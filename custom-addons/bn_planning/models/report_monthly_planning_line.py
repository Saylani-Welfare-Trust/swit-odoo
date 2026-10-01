from odoo import models, fields, api
from odoo.exceptions import ValidationError


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

    display_name = fields.Char(compute='_compute_display_name')

    on_hand_qty = fields.Float(
        string='On Hand', compute='_compute_on_hand_qty',
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

    is_locked = fields.Boolean(
        related='monthly_planning_id.is_locked',
        string='Locked',
        store=False,
    )

    @api.constrains('monthly_planning_id', 'date', 'product_id')
    def _check_locked_plan(self):
        for rec in self:
            if rec.monthly_planning_id.is_locked:
                raise ValidationError(
                    "This Monthly Planning is locked (period ended on %s). "
                    "You cannot add or modify lines."
                    % rec.monthly_planning_id.to_date
                )
                
    def write(self, vals):
        for rec in self:
            if rec.monthly_planning_id.is_locked:
                raise ValidationError(
                    "This Monthly Planning is locked (period ended on %s). "
                    "Lines cannot be modified."
                    % rec.monthly_planning_id.to_date
                )
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.monthly_planning_id.is_locked:
                raise ValidationError(
                    "This Monthly Planning is locked (period ended on %s). "
                    "Lines cannot be deleted."
                    % rec.monthly_planning_id.to_date
                )
        return super().unlink()

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
                    NULL::integer                  AS location_id,
                    k.quantity                     AS quantity
                FROM monthly_planning_kitchen k
                UNION ALL
                SELECT m.id, m.monthly_planning_id, 'madaris', m.date,
                    m.product_id, NULL::integer, m.quantity
                FROM monthly_planning_madaris m
                UNION ALL
                SELECT md.id, md.monthly_planning_id, 'medical', md.date,
                    md.product_id, NULL::integer, md.quantity
                FROM monthly_planning_medical md
                UNION ALL
                SELECT l.id, l.monthly_planning_id, 'livestock', l.date,
                    l.product_id, l.location_id, l.quantity
                FROM monthly_planning_livestock l
                UNION ALL
                SELECT f.id, f.monthly_planning_id, 'food', f.date,
                    f.product_id, NULL::integer, f.quantity
                FROM monthly_planning_food f
                UNION ALL
                SELECT r.id, r.monthly_planning_id, 'ration', r.date,
                    r.product_id, NULL::integer, r.quantity
                FROM monthly_planning_ration r
                UNION ALL
                SELECT mt.id, mt.monthly_planning_id, 'meat', mt.date,
                    mt.product_id, NULL::integer, mt.quantity
                FROM monthly_planning_meat mt
            ) sub
            JOIN monthly_planning mp ON mp.id = sub.monthly_planning_id
            WHERE sub.product_id IS NOT NULL
              AND sub.monthly_planning_id IS NOT NULL
              AND mp.state = 'active';       -- ← only Active plans appear
        """)