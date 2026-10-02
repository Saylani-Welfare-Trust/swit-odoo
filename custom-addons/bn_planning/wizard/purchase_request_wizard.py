from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


TAB_TO_LINE_MODEL = {
    'kitchen':   'monthly.planning.kitchen',
    'madaris':   'monthly.planning.madaris',
    'medical':   'monthly.planning.medical',
    'livestock': 'monthly.planning.livestock',
    'food':      'monthly.planning.food',
    'ration':    'monthly.planning.ration',
    'meat':      'monthly.planning.meat',
}
class MonthlyPlanningPrWizard(models.TransientModel):
    _name = 'monthly.planning.pr.wizard'
    _description = 'Generate Purchase Requisition from Planning Report'

    origin = fields.Char(string='Source', default='Monthly Planning')
    line_ids = fields.One2many(
        'monthly.planning.pr.wizard.line', 'wizard_id',
        string='Products',
    )

    # ── Populate the wizard from the selected report lines ──
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids', [])
        if active_model != 'report.monthly.planning.line' or not active_ids:
            return res

        report_lines = self.env['report.monthly.planning.line'].browse(active_ids)

        # 1) Duplicate check
        already_linked = report_lines.filtered(lambda r: r.purchase_requisition_id)
        if already_linked:
            by_pr = {}
            for rec in already_linked:
                pr = rec.purchase_requisition_id
                by_pr.setdefault(pr.display_name, set()).add(rec.tab)
            lines = []
            for pr_name, tabs in by_pr.items():
                lines.append(
                    "• %s (tabs: %s)" % (pr_name, ", ".join(sorted(tabs)))
                )
            raise ValidationError(_(
                "The following selected line(s) have already been used to "
                "create a Purchase Requisition:\n\n%s\n\n"
                "Clear the reference on those lines first if you really "
                "need to regenerate a PR."
            ) % "\n".join(lines))

        # 2) Aggregate by product
        aggregated = {}
        for line in report_lines:
            product = line.product_id
            if not product:
                continue
            entry = aggregated.get(product.id)
            if entry is None:
                entry = {
                    'product': product,
                    'uom':     product.uom_po_id or product.uom_id,
                    'demand':  0.0,
                    'date':    line.date,
                    'price':   product.standard_price or 0.0,
                    'refs':    [],
                }
                aggregated[product.id] = entry
            entry['demand'] += line.quantity or 0.0
            if line.date and (not entry['date'] or line.date < entry['date']):
                entry['date'] = line.date
            entry['refs'].append("%s:%s" % (line.tab, line.line_id))

        # 3) Compute on-hand and order qty
        source_loc = self.env.ref(
            'stock.stock_location_stock', raise_if_not_found=False
        )
        wiz_lines = []
        for entry in aggregated.values():
            product = entry['product']
            on_hand = (
                product.with_context(location=source_loc.id).qty_available
                if source_loc else 0.0
            )
            order_qty = entry['demand'] - on_hand
            if order_qty < 0:
                order_qty = 0.0

            wiz_lines.append((0, 0, {
                'product_id':    product.id,
                'uom_id':        entry['uom'].id,
                'demand_qty':    entry['demand'],
                'on_hand_qty':   on_hand,
                'order_qty':     order_qty,
                'date_required': entry['date'],
                'price_unit':    entry['price'],
                'source_refs':   ",".join(entry['refs']),
            }))

        res['line_ids'] = wiz_lines
        return res

    # ── Confirm → create the PR ──
    def action_confirm(self):
        self.ensure_one()

        lines = self.line_ids.filtered(
            lambda l: l.product_id and l.order_qty > 0
        )
        if not lines:
            raise ValidationError(_(
                "Nothing to order. All selected products already have "
                "sufficient stock, or the Order Qty is zero."
            ))

        Requisition = self.env['purchase.requisition']
        RequisitionLine = self.env['purchase.requisition.line']

        dates = [l.date_required for l in lines if l.date_required]
        date_start = min(dates) if dates else fields.Date.today()
        date_end   = max(dates) if dates else fields.Date.today()

        pr_vals = {'origin': self.origin or 'Monthly Planning'}
        if 'date_start' in Requisition._fields:
            pr_vals['date_start'] = date_start
        if 'date_end' in Requisition._fields:
            pr_vals['date_end'] = date_end

        mr_id = self.env.context.get('default_material_request_id')
        if mr_id and 'material_request_id' in Requisition._fields:
            pr_vals['material_request_id'] = mr_id

        requisition = Requisition.create(pr_vals)

        pr_line_vals = []
        skipped_no_vendor = []
        for l in lines:
            product = l.product_id
            uom = l.uom_id or product.uom_po_id or product.uom_id

            vals = {
                'requisition_id': requisition.id,
                'product_id':     product.id,
                'product_qty':    l.order_qty,
            }
            if 'product_uom_id' in RequisitionLine._fields:
                vals['product_uom_id'] = uom.id
            elif 'product_uom' in RequisitionLine._fields:
                vals['product_uom'] = uom.id
            if 'date_required' in RequisitionLine._fields and l.date_required:
                vals['date_required'] = l.date_required
            if 'price_unit' in RequisitionLine._fields:
                vals['price_unit'] = l.price_unit or 0.0

            pr_line_vals.append(vals)

            if not product.seller_ids:
                skipped_no_vendor.append(product.display_name)

        RequisitionLine.create(pr_line_vals)

        # Write the PR back on every source line (across tabs)
        for l in lines:
            if not l.source_refs:
                continue
            for ref in l.source_refs.split(','):
                ref = ref.strip()
                if not ref or ':' not in ref:
                    continue
                tab, sid = ref.split(':', 1)
                model_name = TAB_TO_LINE_MODEL.get(tab)
                if not model_name:
                    continue
                try:
                    sid_int = int(sid)
                except ValueError:
                    continue
                self.env[model_name].browse(sid_int).write({
                    'purchase_requisition_id': requisition.id,
                })

        if skipped_no_vendor:
            requisition.message_post(body=_(
                "The following products have no vendor configured. They "
                "will need a vendor before RFQs can be sent: %s"
            ) % ", ".join(skipped_no_vendor))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Requisition'),
            'res_model': 'purchase.requisition',
            'res_id': requisition.id,
            'view_mode': 'form',
            'target': 'current',
        }


class MonthlyPlanningPrWizardLine(models.TransientModel):
    _name = 'monthly.planning.pr.wizard.line'
    _description = 'Purchase Requisition Wizard Line'

    wizard_id = fields.Many2one(
        'monthly.planning.pr.wizard',
        required=True, ondelete='cascade',
    )
    product_id = fields.Many2one('product.product', required=True)
    uom_id = fields.Many2one('uom.uom', string='UoM')
    demand_qty = fields.Float(string='Demand Qty', readonly=True)
    on_hand_qty = fields.Float(string='On Hand Qty', readonly=True)
    order_qty = fields.Float(string='Order Qty')
    date_required = fields.Date(string='Required By')
    price_unit = fields.Float(string='Unit Price')
    source_refs = fields.Char(string='Source Refs', readonly=True)