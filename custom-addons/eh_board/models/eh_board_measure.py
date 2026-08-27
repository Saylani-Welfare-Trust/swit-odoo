# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..lib.formula import compile_formula, FormulaError, ALLOWED_VARIABLES


class EhBoardMeasure(models.Model):
    _name = "eh.board.measure"
    _description = "Dashboard Measure"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    datasource_id = fields.Many2one(
        "eh.board.datasource", string="Data Source",
        required=True, ondelete="cascade")
    model_id = fields.Many2one(related="datasource_id.model_id", store=False)
    field_id = fields.Many2one(
        "ir.model.fields", string="Field", ondelete="cascade",
        domain="[('model_id', '=', model_id), "
               "('ttype', 'in', ('integer', 'float', 'monetary', "
               "'many2one', 'char', 'date', 'datetime', 'boolean'))]",
        help="The field to aggregate. Leave empty for a record count.",
    )
    field_name = fields.Char(related="field_id.name", store=True, readonly=True)
    # For tabular (file / REST) sources the measure points at a parsed column
    # instead of an ir.model.fields - no schema pollution, same spec contract.
    column_id = fields.Many2one(
        "eh.board.source.column", string="Column", ondelete="set null",
        domain="[('datasource_id', '=', datasource_id)]",
        help="The file column to aggregate (for a file data source).")
    aggregate = fields.Selection(
        [("sum", "Sum"), ("avg", "Average"), ("count", "Count"),
         ("count_distinct", "Distinct count"), ("min", "Minimum"),
         ("max", "Maximum"), ("formula", "Calculated (formula)")],
        required=True, default="sum",
    )
    formula = fields.Char(
        help="For a Calculated measure: arithmetic over the item's other "
             "measures as a, b, c ... in order. E.g. 'a / b * 100' for a margin.")

    @api.constrains("aggregate", "formula")
    def _check_formula(self):
        for rec in self:
            if rec.aggregate == "formula":
                try:
                    compiled = compile_formula(rec.formula or "0")
                except FormulaError as err:
                    raise ValidationError(str(err))
                # A misspelled or out-of-range variable (anything but a..f, the
                # positional base measures) would silently evaluate to 0.0 at
                # render time. Reject it at save so the mistake surfaces now.
                unknown = compiled.variables - ALLOWED_VARIABLES
                if unknown:
                    raise ValidationError(
                        "A formula may only reference the base measures a, b, c, "
                        "d, e, f (in order). Unknown name(s): %s."
                        % ", ".join(sorted(unknown)))
    unit = fields.Char(help="Suffix shown after the value, e.g. %, kg, orders.")
    as_line = fields.Boolean(
        string="Show as line",
        help="On a bar chart, draw THIS measure as a line overlay instead of a "
             "bar - a combo chart (e.g. revenue bars + margin-% line).")
    currency_id = fields.Many2one("res.currency")
    number_format = fields.Selection(
        [("plain", "Plain"), ("thousands", "Thousands (K)"),
         ("millions", "Millions (M)"), ("compact", "Compact (K/M/B)")],
        default="compact",
    )
    multiplier = fields.Float(
        default=1.0, help="Scale the raw value, e.g. 0.001 to show thousands.")
    # Lightweight target / comparison used by KPI and gauge items. The full
    # dated-goal and period-comparison machinery lands in a later phase.
    target_value = fields.Float(help="Optional goal used by KPI and gauge items.")
    compare_mode = fields.Selection(
        [("none", "No comparison"), ("prev_period", "Previous period"),
         ("prev_year", "Same period last year")],
        default="none",
    )

    @api.onchange("field_id")
    def _onchange_field_id(self):
        for rec in self:
            if rec.field_id and not rec.name:
                rec.name = rec.field_id.field_description or rec.field_id.name
            if rec.field_id and rec.field_id.ttype in ("many2one", "char", "boolean"):
                # Non-numeric fields can only be counted.
                if rec.aggregate in ("sum", "avg", "min", "max"):
                    rec.aggregate = "count_distinct"

    def measure_key(self):
        self.ensure_one()
        return "m_%s" % (self.id,)

    def apply_scale(self, value):
        self.ensure_one()
        return (value or 0.0) * (self.multiplier or 1.0)
