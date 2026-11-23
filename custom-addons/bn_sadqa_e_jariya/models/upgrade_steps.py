# -*- coding: utf-8 -*-
"""Upgrade steps of Sadqa e Jariya (no migrations folder).

Each step runs once, before the module's data is loaded, when the module is
upgraded from a version older than the step's: the same as a pre-migrate
script. Nothing runs on a fresh install."""
import logging

from odoo import models
from odoo.tools import parse_version
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)
MODULE = 'bn_sadqa_e_jariya'


class SadqaJariya(models.Model):
    _inherit = 'sadqa.jariya'

    def _auto_init(self):
        previous = self._sadqa_installed_version()
        res = super()._auto_init()
        if previous:
            for version, step in (('17.0.2.0', self._upgrade_2_0), ('17.0.2.1', self._upgrade_2_1),
                                  ('17.0.2.3', self._upgrade_2_3), ('17.0.2.4', self._upgrade_2_4)):
                if parse_version(previous) < parse_version(version):
                    _logger.info('%s: upgrade step %s (from %s)', MODULE, version, previous)
                    step()
            self._upgrade_programme_tag()
        return res

    def _upgrade_programme_tag(self):
        """The version built on Welfare had its own tag (sadqa_e_jariya_partner_category,
        "Sadqa e Jariya"), which is no longer in the data and would be deleted with
        its donees' tagging. It becomes the module's tag (sadqa_jariya_partner_category),
        keeping its name, Record Search code, registration settings and donees; if both
        exist, its donees and registration IDs move to the module's tag."""
        cr = self.env.cr

        def tag_id(name):
            cr.execute("""SELECT res_id FROM ir_model_data
                           WHERE module = %s AND name = %s AND model = 'res.partner.category'""", [MODULE, name])
            row = cr.fetchone()
            return row and row[0]

        old, new = tag_id('sadqa_e_jariya_partner_category'), tag_id('sadqa_jariya_partner_category')
        if not old:
            return
        if not new:
            cr.execute("""UPDATE ir_model_data SET name = 'sadqa_jariya_partner_category'
                           WHERE module = %s AND name = 'sadqa_e_jariya_partner_category'
                             AND model = 'res.partner.category'""", [MODULE])
            _logger.info('%s: the Sadqa e Jariya tag %s is kept as sadqa_jariya_partner_category', MODULE, old)
            return
        if old == new:
            return
        cr.execute("""INSERT INTO res_partner_res_partner_category_rel (category_id, partner_id)
                      SELECT %s, partner_id FROM res_partner_res_partner_category_rel WHERE category_id = %s
                      ON CONFLICT DO NOTHING""", [new, old])
        cr.execute("DELETE FROM res_partner_res_partner_category_rel WHERE category_id = %s", [old])
        if table_exists(cr, 'res_partner_registration'):
            # a donee already registered under the module's tag keeps that ID
            cr.execute("""UPDATE res_partner_registration o SET category_id = %s
                           WHERE o.category_id = %s AND NOT EXISTS (
                                 SELECT 1 FROM res_partner_registration n
                                  WHERE n.category_id = %s AND (n.partner_id = o.partner_id OR n.code = o.code))""",
                       [new, old, new])
        cr.execute("SELECT registration_program_code FROM res_partner_category WHERE id = %s", [new])
        if not cr.fetchone()[0]:
            cr.execute("""UPDATE res_partner_category n
                             SET registration_program_code = o.registration_program_code,
                                 registration_role = o.registration_role, registration_kind = o.registration_kind
                            FROM res_partner_category o WHERE n.id = %s AND o.id = %s""", [new, old])
        cr.execute("UPDATE res_partner_category SET registration_program_code = NULL WHERE id = %s", [old])
        # the emptied old tag goes, unless a registration ID still uses it
        in_use = False
        if table_exists(cr, 'res_partner_registration'):
            cr.execute("SELECT 1 FROM res_partner_registration WHERE category_id = %s LIMIT 1", [old])
            in_use = bool(cr.fetchone())
        if not in_use:
            cr.execute("""DELETE FROM ir_model_data WHERE module = %s AND name = 'sadqa_e_jariya_partner_category'
                            AND model = 'res.partner.category'""", [MODULE])
            cr.execute("DELETE FROM res_partner_category WHERE id = %s", [old])
        self.env.invalidate_all()
        _logger.info('%s: donees of the old Sadqa e Jariya tag %s moved to tag %s', MODULE, old, new)

    def _sadqa_installed_version(self):
        """The version installed before this upgrade (None on a fresh install)."""
        self.env.cr.execute("""
            SELECT latest_version FROM ir_module_module
             WHERE name = %s AND state IN ('installed', 'to upgrade', 'to remove')
        """, [MODULE])
        row = self.env.cr.fetchone()
        return row and row[0]

    def _upgrade_2_0(self):
        """Own models instead of extending welfare (only test data existed,
        nothing is moved): the old views on welfare models go, welfare records
        left in Form Sent / Form Filled go back to Completed, the INS/<year>/xxxx
        sequence is kept."""
        cr = self.env.cr
        cr.execute("""
            DELETE FROM ir_ui_view v USING ir_model_data d
             WHERE d.module = %s AND d.model = 'ir.ui.view' AND d.res_id = v.id AND v.model LIKE 'welfare%%'
        """, [MODULE])
        cr.execute("""
            DELETE FROM ir_model_data d
             WHERE d.module = %s AND d.model = 'ir.ui.view'
               AND NOT EXISTS (SELECT 1 FROM ir_ui_view v WHERE v.id = d.res_id)
        """, [MODULE])
        if table_exists(cr, 'welfare'):
            cr.execute("UPDATE welfare SET state = 'completed' WHERE state IN ('form_sent', 'form_filled')")
        cr.execute("""
            UPDATE ir_model_data SET name = 'sadqa_jariya_sequence'
             WHERE module = %s AND name = 'welfare_institution_sequence'
        """, [MODULE])
        cr.execute("UPDATE ir_sequence SET code = 'sadqa.jariya' WHERE code = 'welfare_institution_sequence'")

    def _upgrade_2_1(self):
        """The Cash disbursement category is Bank: its draft branch lines go to the bank."""
        cr = self.env.cr
        cr.execute("""
            SELECT res_id FROM ir_model_data
             WHERE module = %s AND name = 'disbursement_category_cash' AND model = 'sadqa.jariya.disbursement.category'
        """, [MODULE])
        row = cr.fetchone()
        if not row:
            return
        cr.execute("UPDATE sadqa_jariya_disbursement_category SET name = 'Bank' WHERE id = %s", [row[0]])
        for table in ('sadqa_jariya_line', 'sadqa_jariya_recurring_line'):
            if table_exists(cr, table):
                cr.execute("""
                    UPDATE %s SET collection_point = 'bank'
                     WHERE disbursement_category_id = %%s AND collection_point = 'branch' AND state = 'draft'
                """ % table, [row[0]])

    def _upgrade_2_3(self):
        """Construction and Flood are products now: those applications take their institution type."""
        self.env.cr.execute("""
            UPDATE sadqa_jariya SET institution_category = institution_type
             WHERE institution_category IN ('construction', 'flood')
        """)

    def _upgrade_2_4(self):
        """HOD approval comes before the Committee: in-progress applications swap stages."""
        self.env.cr.execute("""
            UPDATE sadqa_jariya
               SET state = CASE state WHEN 'committee_approval' THEN 'hod_approve'
                                      WHEN 'hod_approve' THEN 'committee_approval' END
             WHERE state IN ('committee_approval', 'hod_approve')
        """)
