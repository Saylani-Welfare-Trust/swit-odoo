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
    def action_generate_purchase_requisition(self):
        """Create a draft Purchase Requisition from the selected report lines.

        Works with both the standard purchase.requisition model and the
        customized one used by bn_procurement_workflow — the method only
        writes fields it can actually find on the model.
        """
        if not self:
            raise ValidationError(
                "Please select at least one line before generating a "
                "Purchase Requisition."
            )

        Requisition = self.env['purchase.requisition']
        RequisitionLine = self.env['purchase.requisition.line']

        # ── Date range from selected lines ────────────────
        dates = [ln.date for ln in self if ln.date]
        date_start = min(dates) if dates else fields.Date.today()
        date_end   = max(dates) if dates else fields.Date.today()

        # ── Header values (only set fields that exist) ────
        pr_vals = {'origin': 'Monthly Planning'}

        if 'date_start' in Requisition._fields:
            pr_vals['date_start'] = date_start
        if 'date_end' in Requisition._fields:
            pr_vals['date_end'] = date_end

        # If the caller passes a Material Request via context, link it.
        mr_id = self.env.context.get('default_material_request_id')
        if mr_id and 'material_request_id' in Requisition._fields:
            pr_vals['material_request_id'] = mr_id

        requisition = Requisition.create(pr_vals)

        # ── Build the line items ──────────────────────────
        line_vals_list = []
        skipped_no_vendor = []

        for line in self:
            product = line.product_id
            if not product:
                continue

            uom = product.uom_po_id or product.uom_id

            vals = {
                'requisition_id': requisition.id,
                'product_id': product.id,
                'product_qty': line.quantity or 0.0,
            }

            # Odoo 17 standard uses product_uom_id
            if 'product_uom_id' in RequisitionLine._fields:
                vals['product_uom_id'] = uom.id
            elif 'product_uom' in RequisitionLine._fields:
                vals['product_uom'] = uom.id

            if 'date_required' in RequisitionLine._fields and line.date:
                vals['date_required'] = line.date
            if 'price_unit' in RequisitionLine._fields:
                vals['price_unit'] = product.standard_price or 0.0

            line_vals_list.append(vals)

            # Track products missing a vendor — needed for the later RFQ step
            if not product.seller_ids:
                skipped_no_vendor.append(product.display_name)

        if not line_vals_list:
            # Nothing was created — clean up the empty header and stop
            requisition.unlink()
            raise ValidationError(
                "No valid products found on the selected lines."
            )

        RequisitionLine.create(line_vals_list)

        # Chatter warning for products without a vendor
        if skipped_no_vendor:
            requisition.message_post(body=(
                "The following products have no vendor configured. "
                "They will need a vendor before RFQs can be sent: %s"
            ) % ", ".join(skipped_no_vendor))

        # ── Open the newly created Purchase Requisition ───
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Requisition',
            'res_model': 'purchase.requisition',
            'res_id': requisition.id,
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