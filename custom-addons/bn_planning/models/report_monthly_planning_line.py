from odoo import models, fields, api
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

        - Blocks the action if any selected line is already linked to a PR.
        - Aggregates all selected lines by product → ONE PR line per product
          with the total quantity.
        - Stores the new PR back onto every underlying planning line.
        """
        if not self:
            raise ValidationError(
                "Please select at least one line before generating a "
                "Purchase Requisition."
            )

        # ── 1. Duplicate check ────────────────────────────
        already_linked = self.filtered(lambda r: r.purchase_requisition_id)
        if already_linked:
            by_pr = {}
            for rec in already_linked:
                pr = rec.purchase_requisition_id
                by_pr.setdefault(pr.display_name, set()).add(rec.tab)
            lines = []
            for pr_name, tabs in by_pr.items():
                lines.append(
                    "• %s (used by tabs: %s)"
                    % (pr_name, ", ".join(sorted(tabs)))
                )
            raise ValidationError(
                "The following selected line(s) have already been used to "
                "create a Purchase Requisition:\n\n%s\n\n"
                "Clear the reference on those lines first if you really need "
                "to regenerate a PR."
                % "\n".join(lines)
            )

        # ── 2. Aggregate the selected lines by product ────
        #    product_id  →  {
        #       'product':  product.product record,
        #       'uom':      uom.product.uom,
        #       'qty':      summed float,
        #       'date':     earliest date found (for date_required),
        #       'price':    product.standard_price,
        #    }
        aggregated = {}

        for line in self:
            product = line.product_id
            if not product:
                continue
            key = product.id
            entry = aggregated.get(key)
            if entry is None:
                entry = {
                    'product': product,
                    'uom':     product.uom_po_id or product.uom_id,
                    'qty':     0.0,
                    'date':    line.date,
                    'price':   product.standard_price or 0.0,
                }
                aggregated[key] = entry

            entry['qty'] += line.quantity or 0.0

            # keep the earliest date_required among duplicates
            if line.date and (not entry['date'] or line.date < entry['date']):
                entry['date'] = line.date

        if not aggregated:
            raise ValidationError(
                "No valid products found on the selected lines."
            )

        # ── 3. Build the PR header ────────────────────────
        Requisition = self.env['purchase.requisition']
        RequisitionLine = self.env['purchase.requisition.line']

        all_dates = [e['date'] for e in aggregated.values() if e['date']]
        date_start = min(all_dates) if all_dates else fields.Date.today()
        date_end   = max(all_dates) if all_dates else fields.Date.today()

        pr_vals = {'origin': 'Monthly Planning'}
        if 'date_start' in Requisition._fields:
            pr_vals['date_start'] = date_start
        if 'date_end' in Requisition._fields:
            pr_vals['date_end'] = date_end

        mr_id = self.env.context.get('default_material_request_id')
        if mr_id and 'material_request_id' in Requisition._fields:
            pr_vals['material_request_id'] = mr_id

        requisition = Requisition.create(pr_vals)

        # ── 4. One PR line per product ────────────────────
        line_vals_list = []
        skipped_no_vendor = []

        for entry in aggregated.values():
            product = entry['product']
            uom = entry['uom']

            vals = {
                'requisition_id': requisition.id,
                'product_id': product.id,
                'product_qty': entry['qty'],
            }
            if 'product_uom_id' in RequisitionLine._fields:
                vals['product_uom_id'] = uom.id
            elif 'product_uom' in RequisitionLine._fields:
                vals['product_uom'] = uom.id
            if 'date_required' in RequisitionLine._fields and entry['date']:
                vals['date_required'] = entry['date']
            if 'price_unit' in RequisitionLine._fields:
                vals['price_unit'] = entry['price']

            line_vals_list.append(vals)

            if not product.seller_ids:
                skipped_no_vendor.append(product.display_name)

        RequisitionLine.create(line_vals_list)

        # ── 5. Write the PR reference back on the source lines ──
        for rec in self:
            if not rec.tab or not rec.line_id:
                continue
            model_name = TAB_TO_LINE_MODEL.get(rec.tab)
            if not model_name:
                continue
            self.env[model_name].browse(rec.line_id).write({
                'purchase_requisition_id': requisition.id,
            })

        # ── 6. Chatter warning for missing vendors ────────
        if skipped_no_vendor:
            requisition.message_post(body=(
                "The following products have no vendor configured. "
                "They will need a vendor before RFQs can be sent: %s"
            ) % ", ".join(skipped_no_vendor))

        # ── 7. Open the new PR ────────────────────────────
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
                    k.planned_qty                  AS planned_qty,
                    k.purchase_requisition_id      AS purchase_requisition_id
                FROM monthly_planning_kitchen k
                UNION ALL
                SELECT m.id, m.monthly_planning_id, 'madaris', m.date,
                    m.product_id, NULL::integer, m.quantity, m.planned_qty,
                    m.purchase_requisition_id
                FROM monthly_planning_madaris m
                UNION ALL
                SELECT md.id, md.monthly_planning_id, 'medical', md.date,
                    md.product_id, NULL::integer, md.quantity, md.planned_qty,
                    md.purchase_requisition_id
                FROM monthly_planning_medical md
                UNION ALL
                SELECT l.id, l.monthly_planning_id, 'livestock', l.date,
                    l.product_id, l.location_id, l.quantity, l.planned_qty,
                    l.purchase_requisition_id
                FROM monthly_planning_livestock l
                UNION ALL
                SELECT f.id, f.monthly_planning_id, 'food', f.date,
                    f.product_id, NULL::integer, f.quantity, f.planned_qty,
                    f.purchase_requisition_id
                FROM monthly_planning_food f
                UNION ALL
                SELECT r.id, r.monthly_planning_id, 'ration', r.date,
                    r.product_id, NULL::integer, r.quantity, r.planned_qty,
                    r.purchase_requisition_id
                FROM monthly_planning_ration r
                UNION ALL
                SELECT mt.id, mt.monthly_planning_id, 'meat', mt.date,
                    mt.product_id, NULL::integer, mt.quantity, mt.planned_qty,
                    mt.purchase_requisition_id
                FROM monthly_planning_meat mt
            ) sub
            JOIN monthly_planning mp ON mp.id = sub.monthly_planning_id
            WHERE sub.product_id IS NOT NULL
              AND sub.monthly_planning_id IS NOT NULL
              AND mp.state = 'active';
        """)