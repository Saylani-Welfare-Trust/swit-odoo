# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Regression tests for the SECOND hardening pass (defects the first fixes
introduced or left). Each pins a specific regression so it cannot come back.
"""
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError

from ..lib import tabular, aggregation
from ..datasources.sql import SqlDataSource


@tagged("post_install", "-at_install", "eh_board")
class TestBoardFixes2(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Dashboard = cls.env["eh.board.dashboard"]
        cls.Datasource = cls.env["eh.board.datasource"]
        cls.Measure = cls.env["eh.board.measure"]
        cls.Item = cls.env["eh.board.item"]
        cls.partner_model = cls.env["ir.model"]._get("res.partner")
        cls.country_field = cls.env["ir.model.fields"]._get("res.partner", "country_id")
        cls.au = cls.env.ref("base.au", raise_if_not_found=False)
        cls.us = cls.env.ref("base.us", raise_if_not_found=False)
        cls.de = cls.env.ref("base.de", raise_if_not_found=False)
        Partner = cls.env["res.partner"]
        # A clear count distribution: US=5, AU=3, DE=1 (+ any pre-existing).
        recs = []
        for c, n in ((cls.us, 5), (cls.au, 3), (cls.de, 1)):
            for i in range(n):
                recs.append({"name": "P-%s-%d" % (c.code if c else "x", i),
                             "country_id": c.id if c else False})
        cls.partners = Partner.create(recs)
        cls.source = cls.Datasource.create({
            "name": "Partners", "provider_type": "orm",
            "model_id": cls.partner_model.id,
            "domain": "[('id', 'in', %s)]" % cls.partners.ids})
        cls.count = cls.Measure.create({
            "name": "Records", "datasource_id": cls.source.id, "aggregate": "count"})

    # ---- SQL sandbox: the comment-strip bypass is closed --------------------
    def _err(self, q):
        return SqlDataSource()._validate_sql(q)

    def test_sql_comments_rejected(self):
        """SQL comments are refused outright, so a `--` / `/* */` inside a string
        literal can no longer desync the scanned text from what executes."""
        self.assertTrue(self._err("SELECT '/*' AS a, pg_read_file('/x') AS b, '*/' AS c"))
        self.assertTrue(self._err("SELECT (SELECT 1 WHERE 'q'='--') AS a, "
                                  "(SELECT 1 FROM res_users) AS b"))
        self.assertTrue(self._err("SELECT 1 -- comment\nFROM t"))

    def test_sql_raw_scan_still_blocks_sensitive(self):
        self.assertTrue(self._err("SELECT login FROM res_users"))
        self.assertTrue(self._err("SELECT nextval('s')"))
        self.assertTrue(self._err('SELECT * FROM u&"\\0072es_users"'))
        self.assertIsNone(self._err("SELECT name, count(*) FROM x GROUP BY name"))

    # ---- exact top-N is correct on this Odoo version -----------------------
    def test_value_sorted_top_n_is_the_true_top_n(self):
        """value_desc + a record limit returns the TRUE top groups, whether the
        DB-order push is used (Odoo 17+) or the safe read+sort path (Odoo 16)."""
        spec = {"model": "res.partner", "domain": [("id", "in", self.partners.ids)],
                "dimensions": [{"field": "country_id", "granularity": None}],
                "measures": [{"key": "m", "field": None, "verb": "count", "multiplier": 1.0}],
                "measure_keys": ["m"], "sort": "value_desc", "limit": 2,
                "read_cap": None, "group_others": False, "cumulative": False,
                "fill_gaps": False}
        from ..datasources.orm import OrmDataSource
        res = OrmDataSource().aggregate(self.source, spec)
        counts = [round(r["values"]["m"]) for r in res["rows"]]
        # top-2 by count must be US(5), AU(3) - never DE(1) or an arbitrary slice.
        self.assertEqual(counts, [5, 3])

    # ---- pivot field-sort margins do not blank -----------------------------
    def test_pivot_field_sort_margins_reconcile(self):
        """A pivot sorted by a specific field must still show exact margins; the
        dedicated margin reads must not inherit the field-sort order (which would
        raise on the reduced group-by and blank the totals)."""
        item = self.Item.create({
            "dashboard_id": self.Dashboard.create({"name": "d"}).id,
            "item_type": "pivot", "title": "pv", "datasource_id": self.source.id,
            "measure_ids": [(6, 0, self.count.ids)],
            "primary_dimension_id": self.country_field.id,
            "sort_mode": "field", "sort_field_id": self.country_field.id,
            "sort_order": "desc"})
        p = item.get_payload()
        self.assertIsNone(p.get("error"))
        mk = p["measure_keys"][0]
        # grand total = all 9 records, and row totals sum to it (not 0).
        self.assertEqual(round(p["grand_total"][mk]), 9)
        rowsum = sum(round(rt.get(mk, 0)) for rt in p["row_totals"].values())
        self.assertEqual(rowsum, 9)

    # ---- an unsaved dashboard cannot create an item with a null dashboard_id --
    def test_add_widget_on_unsaved_board_raises_clean(self):
        """Creating a widget against a non-persisted (NewId) dashboard raises a
        clear UserError instead of a raw not-null constraint violation."""
        newD = self.Dashboard.browse([None])
        vals = {"item_type": "tile", "title": "X",
                "model_id": self.partner_model.id,
                "measures": [{"verb": "count", "field": None}]}
        with self.assertRaises(UserError):
            newD._create_item_from_builder(dict(vals))

    def test_dashboard_id_is_authoritative(self):
        """A dashboard_id in the client vals can never override the real board."""
        D = self.Dashboard.create({"name": "d"})
        item = D._create_item_from_builder({
            "item_type": "tile", "title": "X", "dashboard_id": False,
            "model_id": self.partner_model.id,
            "measures": [{"verb": "count", "field": None}]})
        self.assertEqual(item.dashboard_id.id, D.id)

    # ---- tabular UTF-16 BOM is consumed, not left on the header -------------
    def test_utf16_bom_stripped_from_header(self):
        raw = "name,value\nAlice,1\nBob,2\n".encode("utf-16")  # includes BOM
        parsed = tabular.parse_csv(raw)
        names = [c["name"] for c in parsed["columns"]]
        # first column key is "name", not "﻿name"
        self.assertIn("name", names)
        self.assertFalse(any("﻿" in n for n in names))
