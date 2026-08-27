# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
import logging

from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EhBoardTemplate(models.Model):
    """A ready-made dashboard, predefined or captured from a live board.

    The vertical packs (Contacts, CRM/Sales, Accounting, Warehouse, Point of
    Sale and HR) ship as predefined templates: their payload names target models
    as strings, so a template stays inert until its base app is installed - which
    is how the one module can bundle every vertical without hard-depending on
    every app.
    """
    _name = "eh.board.template"
    _description = "Dashboard Template"
    _order = "category, sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    category = fields.Selection(
        [("general", "General"), ("account", "Accounting"), ("crm", "Sales & CRM"),
         ("pos", "Point of Sale"), ("stock", "Inventory"), ("hr", "Human Resources"),
         ("web", "Website")], default="general")
    is_predefined = fields.Boolean()
    required_module = fields.Char(
        help="Technical name of the base app a vertical template needs "
             "(e.g. account). Blank for a general template.")
    description = fields.Text()
    payload = fields.Json(default=lambda self: {})

    def is_available(self):
        """True when the base app this template targets is installed."""
        self.ensure_one()
        if not self.required_module:
            return True
        module = self.env["ir.module.module"].sudo().search(
            [("name", "=", self.required_module)], limit=1)
        return bool(module) and module.state == "installed"

    # -- apply --------------------------------------------------------------
    def create_from_template(self):
        """Materialise a live dashboard from this template's payload.

        Every item is created through the same builder path a hand-built widget
        uses, so measures/datasources are deduped and record rules apply. Items
        whose model or field is absent on this database are skipped rather than
        failing the whole apply - which is how one pack works across versions.
        """
        self.ensure_one()
        if not self.is_available():
            raise UserError(_(
                "This template needs the %s app. Install it first.",
                self.required_module))
        payload = self.payload or {}
        Dashboard = self.env["eh.board.dashboard"]
        dash = Dashboard.create({
            "name": payload.get("name") or self.name, "state": "draft"})
        grid = {}
        first_model = None
        for spec in payload.get("items", []):
            try:
                item = self._materialise_item(dash, spec)
            except Exception as err:  # noqa: BLE001 - skip, never break the apply
                _logger.info("eh_board template item skipped: %s", err)
                continue
            if not item:
                continue
            grid[str(item.id)] = {
                "x": spec.get("x", 0), "y": spec.get("y", 0),
                "w": spec.get("w", 4), "h": spec.get("h", 6)}
            if not first_model and spec.get("model"):
                first_model = spec.get("model")
        self.env["eh.board.layout.version"].create({
            "dashboard_id": dash.id, "name": "Default",
            "is_active": True, "is_default": True, "grid": grid})
        for flt in payload.get("filters", []):
            self._materialise_filter(dash, flt, first_model)
        return dash

    def _materialise_item(self, dash, spec):
        model = spec.get("model")
        if model and model not in self.env:
            return None  # base app not installed -> skip this widget
        vals = {
            "item_type": spec.get("type", "bar"),
            "title": spec.get("title", ""),
        }
        for key in ("accent", "tile_style", "content", "domain", "icon"):
            if spec.get(key):
                vals[key] = spec[key]
        if model:
            model_rec = self.env["ir.model"]._get(model)
            model_obj = self.env[model]
            vals["model_id"] = model_rec.id
            measures = spec.get("measures") or ([spec["measure"]] if spec.get("measure") else [])
            # Drop measures whose field is absent on this version.
            measures = [m for m in measures
                        if not m.get("field") or m["field"] in model_obj._fields]
            if measures:
                vals["measures"] = measures
            dim = spec.get("dimension")
            if dim:
                if dim in model_obj._fields:
                    vals["dimension"] = dim
                    if model_obj._fields[dim].type in ("date", "datetime"):
                        vals["granularity"] = spec.get("granularity", "month")
                elif spec.get("type") not in ("kpi", "tile", "gauge", "richtext", "todo"):
                    return None  # a chart lost its group-by on this version -> skip
            sec = spec.get("secondary_dimension")
            if sec and sec in model_obj._fields:
                vals["secondary_dimension"] = sec
        return dash._create_item_from_builder(vals)

    def _materialise_filter(self, dash, flt, first_model):
        model = flt.get("model") or first_model
        field_name = flt.get("field")
        if not (model and field_name and model in self.env):
            return
        if field_name not in self.env[model]._fields:
            return
        model_rec = self.env["ir.model"]._get(model)
        field = self.env["ir.model.fields"].search(
            [("model_id", "=", model_rec.id), ("name", "=", field_name)], limit=1)
        if not field:
            return
        self.env["eh.board.filter"].create({
            "dashboard_id": dash.id,
            "name": flt.get("name") or field.field_description or field_name,
            "filter_type": "field", "field_id": field.id})

    def apply_and_open(self):
        """Create the dashboard and return an action opening it on the board."""
        self.ensure_one()
        dash = self.create_from_template()
        return {
            "type": "ir.actions.client",
            "tag": "eh_board.board",
            "name": dash.name,
            "params": {"dashboard_id": dash.id},
        }

    def gallery(self):
        """Available templates for the picker, availability resolved."""
        return [{
            "id": t.id, "name": t.name, "category": t.category,
            "description": t.description or "",
            "required_module": t.required_module or "",
            "available": t.is_available(),
        } for t in self.search([])]

    # -- predefined vertical packs ------------------------------------------
    @staticmethod
    def _pack_items(model, heading, sum_field=None, cat_dim=None,
                    second_dim=None, date_field=None):
        """Build the standard vertical layout: heading, a count tile, an
        optional value KPI, a category bar, and a time series / split."""
        items = [
            {"type": "richtext", "title": "",
             "content": "<h2>%s</h2>" % heading, "x": 0, "y": 0, "w": 12, "h": 2},
            {"type": "tile", "title": "Total records", "model": model,
             "measure": {"verb": "count"}, "accent": "mint", "tile_style": "solid",
             "icon": "fa-hashtag", "x": 0, "y": 2, "w": 3, "h": 4},
        ]
        x = 3
        if sum_field:
            items.append({"type": "kpi", "title": "Total value", "model": model,
                          "measure": {"verb": "sum", "field": sum_field},
                          "accent": "blue", "x": 3, "y": 2, "w": 3, "h": 4})
            x = 6
        if cat_dim:
            items.append({"type": "bar", "title": "By category", "model": model,
                          "measure": {"verb": "count"}, "dimension": cat_dim,
                          "accent": "violet", "x": x, "y": 2, "w": 12 - x, "h": 4})
        if date_field:
            items.append({"type": "area", "title": "Over time", "model": model,
                          "measure": {"verb": "count"}, "dimension": date_field,
                          "granularity": "month", "accent": "teal",
                          "x": 0, "y": 6, "w": 8, "h": 6})
            if second_dim:
                items.append({"type": "doughnut", "title": "Split", "model": model,
                              "measure": {"verb": "count"}, "dimension": second_dim,
                              "accent": "amber", "x": 8, "y": 6, "w": 4, "h": 6})
        elif second_dim:
            items.append({"type": "doughnut", "title": "Split", "model": model,
                          "measure": {"verb": "count"}, "dimension": second_dim,
                          "accent": "amber", "x": 0, "y": 6, "w": 6, "h": 6})
        return items

    def _seed_predefined(self):
        """Ship the six vertical packs once. Each targets a base app by string
        and stays inert (greyed in the gallery) until that app is installed."""
        if self.search_count([("is_predefined", "=", True)]):
            return
        P = self._pack_items
        packs = [
            ("Contacts overview", "general", "", "res.partner",
             P("res.partner", "Contacts overview", None, "country_id", "is_company", "create_date"),
             {"name": "Country", "field": "country_id"}),
            ("Sales & CRM pipeline", "crm", "crm", "crm.lead",
             P("crm.lead", "Sales pipeline", "expected_revenue", "stage_id", "type", "create_date"),
             {"name": "Salesperson", "field": "user_id"}),
            ("Sales overview", "crm", "sale", "sale.order",
             P("sale.order", "Sales overview", "amount_total", "state", "user_id", "date_order"),
             {"name": "Salesperson", "field": "user_id"}),
            ("Accounting overview", "account", "account", "account.move",
             P("account.move", "Accounting", "amount_total", "move_type", "state", "invoice_date"),
             {"name": "Journal", "field": "journal_id"}),
            ("Warehouse operations", "stock", "stock", "stock.picking",
             P("stock.picking", "Warehouse operations", None, "state", "picking_type_id", "scheduled_date"),
             {"name": "Operation type", "field": "picking_type_id"}),
            ("Point of Sale", "pos", "point_of_sale", "pos.order",
             P("pos.order", "Point of Sale", "amount_total", "state", None, "date_order"),
             {"name": "Session", "field": "session_id"}),
            ("Human Resources", "hr", "hr", "hr.employee",
             P("hr.employee", "Human Resources", None, "department_id", "job_id", None),
             {"name": "Department", "field": "department_id"}),
        ]
        for name, cat, mod, model, items, flt in packs:
            self.create({
                "name": name, "category": cat, "is_predefined": True,
                "required_module": mod,
                "description": "Ready-made %s dashboard. Install %s to use it." % (name, mod),
                "payload": {"name": name, "items": items,
                            "filters": [dict(flt, model=model)]},
            })
