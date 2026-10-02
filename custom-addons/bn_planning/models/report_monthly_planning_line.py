from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, time as dtime
import logging

_logger = logging.getLogger(__name__)


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
    def action_generate_purchase_request(self):
        """Create ONE draft Purchase Request from the selected lines."""
        if not self:
            raise ValidationError(
                "Please select at least one line before generating a Purchase Request."
            )

        # Optional guard — make sure OCA purchase_request module is installed
        if 'purchase.request' not in self.env:
            raise ValidationError(
                "The Purchase Request module is not installed on this database."
            )

        PurchaseRequest = self.env['purchase.request']
        PurchaseRequestLine = self.env['purchase.request.line']

        # Requested by = current user's employee, fallback to current user
        employee = self.env['hr.employee'].search(
            [('user_id', '=', self.env.uid)], limit=1
        )

        # Earliest / latest line dates become the request's date window
        dates = [ln.date for ln in self if ln.date]
        date_start = min(dates) if dates else fields.Date.today()
        date_end = max(dates) if dates else fields.Date.today()

        # ── Build the request header ──────────────────────
        pr_vals = {
            'origin': 'Monthly Planning',
            'date_start': date_start,
            'date_end': date_end,
        }
        # These fields exist in OCA PR — set them if present
        if 'requested_by' in PurchaseRequest._fields and employee:
            pr_vals['requested_by'] = employee.id
        if 'description' in PurchaseRequest._fields:
            pr_vals['description'] = (
                "Auto-generated from Monthly Planning report."
            )

        pr = PurchaseRequest.create(pr_vals)

        # ── Build the request lines ───────────────────────
        no_vendor_products = []
        created_lines = self.env['purchase.request.line']

        for line in self:
            product = line.product_id
            if not product:
                continue

            # Warn if product has no vendor (useful for the later RFQ step)
            if not product.seller_ids:
                no_vendor_products.append(product.display_name)

            uom = product.uom_po_id or product.uom_id

            line_vals = {
                'request_id': pr.id,
                'product_id': product.id,
                'product_qty': line.quantity or 0.0,
                'product_uom_id': uom.id,
                'name': product.display_name,
                'date_required': line.date or fields.Date.today(),
            }
            # Some OCA versions expect a different field name
            if 'uom_id' in PurchaseRequestLine._fields and \
               'product_uom_id' not in PurchaseRequestLine._fields:
                line_vals.pop('product_uom_id', None)
                line_vals['uom_id'] = uom.id

            created_lines |= PurchaseRequestLine.create(line_vals)

        # Log the products without a vendor onto the request's chatter
        if no_vendor_products:
            pr.message_post(
                body="Products without a configured vendor: %s"
                     % ", ".join(no_vendor_products)
            )

        # ── Open the newly created Purchase Request ───────
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Request',
            'res_model': 'purchase.request',
            'res_id': pr.id,
            'view_mode': 'form',
            'target': 'current',
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
                    NULL::integer                  AS location_id,
                    k.quantity                     AS quantity,
                    k.planned_qty                  AS planned_qty
                FROM monthly_planning_kitchen k
                UNION ALL
                SELECT m.id, m.monthly_planning_id, 'madaris', m.date,
                    m.product_id, NULL::integer, m.quantity, m.planned_qty
                FROM monthly_planning_madaris m
                UNION ALL
                SELECT md.id, md.monthly_planning_id, 'medical', md.date,
                    md.product_id, NULL::integer, md.quantity, md.planned_qty
                FROM monthly_planning_medical md
                UNION ALL
                SELECT l.id, l.monthly_planning_id, 'livestock', l.date,
                    l.product_id, l.location_id, l.quantity, l.planned_qty
                FROM monthly_planning_livestock l
                UNION ALL
                SELECT f.id, f.monthly_planning_id, 'food', f.date,
                    f.product_id, NULL::integer, f.quantity, f.planned_qty
                FROM monthly_planning_food f
                UNION ALL
                SELECT r.id, r.monthly_planning_id, 'ration', r.date,
                    r.product_id, NULL::integer, r.quantity, r.planned_qty
                FROM monthly_planning_ration r
                UNION ALL
                SELECT mt.id, mt.monthly_planning_id, 'meat', mt.date,
                    mt.product_id, NULL::integer, mt.quantity, mt.planned_qty
                FROM monthly_planning_meat mt
            ) sub
            JOIN monthly_planning mp ON mp.id = sub.monthly_planning_id
            WHERE sub.product_id IS NOT NULL
              AND sub.monthly_planning_id IS NOT NULL
              AND mp.state = 'active';
        """)