from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time as dtime
import logging

_logger = logging.getLogger(__name__)

TAB_TO_LINE_MODEL = {
    'kitchen':   'monthly.planning.kitchen',
    'madaris':   'monthly.planning.madaris',
    'medical':   'monthly.planning.medical',
    'livestock': 'monthly.planning.livestock',
    'food':      'monthly.planning.food',
    'ration':    'monthly.planning.ration',
    'meat':      'monthly.planning.meat',
}

class ReportMonthlyPlanningLine(models.Model):
    _name = 'report.monthly.planning.line'
    _description = 'Monthly Planning Lines (Report)'
    _auto = False
    _order = 'monthly_planning_id, tab, date, id'
    _rec_name = 'display_name'

    # ── Parent info ────────────────────────────────────
    monthly_planning_id = fields.Many2one(
        'monthly.planning', string='Monthly Planning', readonly=True,
    )
    from_date = fields.Date(
        related='monthly_planning_id.from_date', string='From Date', store=False,
    )
    to_date = fields.Date(
        related='monthly_planning_id.to_date', string='To Date', store=False,
    )

    # ── Line info ──────────────────────────────────────
    tab = fields.Selection(
        selection=[
            ('kitchen',   'Kitchen'),
            ('madaris',   'Madaris'),
            ('medical',   'Medical'),
            ('livestock', 'Livestock'),
            ('food',      'Food'),
            ('ration',    'Ration'),
            ('meat',      'Meat'),
        ],
        string='Tab', readonly=True,
    )
    date = fields.Date(string='Date', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    location_id = fields.Many2one('stock.location', string='Location', readonly=True)
    quantity = fields.Float(string='Quantity', readonly=True)
    planned_qty = fields.Float(string='Planned Qty', readonly=True)

    display_name = fields.Char(compute='_compute_display_name')

    on_hand_qty = fields.Float(
        string='On Hand', compute='_compute_on_hand_qty',
    )

    qty_diff = fields.Float(
        string='Difference', compute='_compute_qty_diff',
    )

    is_locked = fields.Boolean(
        related='monthly_planning_id.is_locked',
        string='Locked', store=False,
    )

    line_id = fields.Integer(
        string='Source Line ID', readonly=True,
        help='ID of the underlying monthly.planning.* line.',
    )
    purchase_requisition_id = fields.Many2one(
        'purchase.requisition',
        string='Purchase Requisition',
        readonly=True,
    )
    transfer_picking_id = fields.Many2one(
            'stock.picking', string='Internal Transfer', readonly=True,
        )
    @api.depends('product_id', 'tab')
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.product_id.display_name or '', rec.tab or '']
            rec.display_name = ' – '.join([p for p in parts if p])

    @api.depends('product_id')
    def _compute_on_hand_qty(self):
        source_loc = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        for rec in self:
            if rec.product_id and source_loc:
                rec.on_hand_qty = rec.product_id.with_context(
                    location=source_loc.id
                ).qty_available
            else:
                rec.on_hand_qty = 0.0

    @api.depends('quantity', 'planned_qty')
    def _compute_qty_diff(self):
        for rec in self:
            rec.qty_diff = (rec.quantity or 0.0) - (rec.planned_qty or 0.0)

    # ── PR generation ─────────────────────────────────
    def action_generate_purchase_requisition(self):
        """Open the wizard that shows Demand / On Hand / Order Qty."""
        if not self:
            raise ValidationError(
                _("Please select at least one line before generating a "
                  "Purchase Requisition.")
            )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Purchase Requisition'),
            'res_model': 'monthly.planning.pr.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'report.monthly.planning.line',
                'active_ids': self.ids,
            },
        }

    def action_generate_difference_purchase_requisition(self):
        """Open the wizard in 'difference' mode.

        Unlike the normal action, this one ALLOWS already-linked lines to be
        selected — that's the entire point. The wizard will subtract what has
        already been ordered via prior PRs and only propose the shortfall.
        """
        if not self:
            raise ValidationError(_(
                "Please select at least one line before generating a "
                "difference Purchase Requisition."
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Difference Purchase Requisition'),
            'res_model': 'monthly.planning.pr.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'report.monthly.planning.line',
                'active_ids': self.ids,
                'default_mode': 'difference',
            },
        }
    # ── SQL view definition ────────────────────────────
    def init(self):
        self.env.cr.execute("""
            DROP VIEW IF EXISTS report_monthly_planning_line CASCADE;

            CREATE VIEW report_monthly_planning_line AS
            SELECT ROW_NUMBER() OVER () AS id, sub.*
            FROM (
                SELECT
                    k.id                           AS line_id,
                    k.monthly_planning_id          AS monthly_planning_id,
                    'kitchen'                      AS tab,
                    k.date                         AS date,
                    k.product_id                   AS product_id,
                    k.location_id                  AS location_id,
                    k.quantity                     AS quantity,
                    k.planned_qty                  AS planned_qty,
                    k.purchase_requisition_id      AS purchase_requisition_id,
                    k.transfer_picking_id          AS transfer_picking_id
                FROM monthly_planning_kitchen k
                UNION ALL
                SELECT m.id, m.monthly_planning_id, 'madaris', m.date,
                    m.product_id, m.location_id, m.quantity, m.planned_qty,
                    m.purchase_requisition_id, m.transfer_picking_id
                FROM monthly_planning_madaris m
                UNION ALL
                SELECT md.id, md.monthly_planning_id, 'medical', md.date,
                    md.product_id, md.location_id, md.quantity, md.planned_qty,
                    md.purchase_requisition_id, md.transfer_picking_id
                FROM monthly_planning_medical md
                UNION ALL
                SELECT l.id, l.monthly_planning_id, 'livestock', l.date,
                    l.product_id, l.location_id, l.quantity, l.planned_qty,
                    l.purchase_requisition_id, l.transfer_picking_id
                FROM monthly_planning_livestock l
                UNION ALL
                SELECT f.id, f.monthly_planning_id, 'food', f.date,
                    f.product_id, f.location_id, f.quantity, f.planned_qty,
                    f.purchase_requisition_id, f.transfer_picking_id
                FROM monthly_planning_food f
                UNION ALL
                SELECT r.id, r.monthly_planning_id, 'ration', r.date,
                    r.product_id, r.location_id, r.quantity, r.planned_qty,
                    r.purchase_requisition_id, r.transfer_picking_id
                FROM monthly_planning_ration r
                UNION ALL
                SELECT mt.id, mt.monthly_planning_id, 'meat', mt.date,
                    mt.product_id, mt.location_id, mt.quantity, mt.planned_qty,
                    mt.purchase_requisition_id, mt.transfer_picking_id
                FROM monthly_planning_meat mt
            ) sub
            JOIN monthly_planning mp ON mp.id = sub.monthly_planning_id
            WHERE sub.product_id IS NOT NULL
              AND sub.monthly_planning_id IS NOT NULL
              AND mp.state = 'active';
        """)
        self.env.cr.execute("""
            DROP VIEW IF EXISTS report_monthly_planning_line CASCADE;

            CREATE VIEW report_monthly_planning_line AS
            SELECT ROW_NUMBER() OVER () AS id, sub.*
            FROM (
                SELECT
                    k.id                           AS line_id,
                    k.monthly_planning_id          AS monthly_planning_id,
                    'kitchen'                      AS tab,
                    k.date                         AS date,
                    k.product_id                   AS product_id,
                    k.location_id                  AS location_id,
                    k.quantity                     AS quantity,
                    k.planned_qty                  AS planned_qty,
                    k.purchase_requisition_id      AS purchase_requisition_id
                FROM monthly_planning_kitchen k
                UNION ALL
                SELECT m.id, m.monthly_planning_id, 'madaris', m.date,
                    m.product_id, m.location_id, m.quantity, m.planned_qty,
                    m.purchase_requisition_id
                FROM monthly_planning_madaris m
                UNION ALL
                SELECT md.id, md.monthly_planning_id, 'medical', md.date,
                    md.product_id, md.location_id, md.quantity, md.planned_qty,
                    md.purchase_requisition_id
                FROM monthly_planning_medical md
                UNION ALL
                SELECT l.id, l.monthly_planning_id, 'livestock', l.date,
                    l.product_id, l.location_id, l.quantity, l.planned_qty,
                    l.purchase_requisition_id
                FROM monthly_planning_livestock l
                UNION ALL
                SELECT f.id, f.monthly_planning_id, 'food', f.date,
                    f.product_id, f.location_id, f.quantity, f.planned_qty,
                    f.purchase_requisition_id
                FROM monthly_planning_food f
                UNION ALL
                SELECT r.id, r.monthly_planning_id, 'ration', r.date,
                    r.product_id, r.location_id, r.quantity, r.planned_qty,
                    r.purchase_requisition_id
                FROM monthly_planning_ration r
                UNION ALL
                SELECT mt.id, mt.monthly_planning_id, 'meat', mt.date,
                    mt.product_id, mt.location_id, mt.quantity, mt.planned_qty,
                    mt.purchase_requisition_id
                FROM monthly_planning_meat mt
            ) sub
            JOIN monthly_planning mp ON mp.id = sub.monthly_planning_id
            WHERE sub.product_id IS NOT NULL
              AND sub.monthly_planning_id IS NOT NULL
              AND mp.state = 'active';
        """)