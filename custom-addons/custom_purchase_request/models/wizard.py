from odoo import models, fields, api
from odoo.exceptions import ValidationError


class VendorPurchaseWizard(models.TransientModel):
    _name = 'vendor.purchase.wizard'
    _description = 'Vendor Purchase Wizard'

    request_id = fields.Many2one('custom.purchase.request', string="Purchase Request")
    line_ids = fields.One2many('vendor.purchase.wizard.line', 'wizard_id', string="Vendor Lines")
    purchase_order_ids = fields.Many2many('purchase.order', string="Selected Purchase Orders", readonly=True)

    summary_line_ids = fields.One2many(
        'vendor.purchase.wizard.summary.line',
        'wizard_id',
        string='Product‑Vendor Matrix',
        compute='_compute_summary_lines',
        )

    summary = fields.Text(
        string="Recommendation Summary",
        compute='_compute_summary',
        store=True)

    from odoo.exceptions import ValidationError
    @api.depends('line_ids.vendor_unit_price', 'line_ids.quantity', 'line_ids.vendor_lead_time')
    def _compute_summary_lines(self):
        for wiz in self:
            # Clear existing summary lines
            wiz.summary_line_ids = [(5, 0, 0)]

            entries = []
            for line in wiz.line_ids:
                total = (line.vendor_unit_price or 0.0) * (line.quantity or 0.0)
                entries.append({
                    'product': line.product_id,
                    'vendor': line.vendor_id,
                    'unit_price': line.vendor_unit_price,
                    'qty': line.quantity,
                    'total': total,
                    'lead': line.vendor_lead_time or 0,
                })

            from collections import defaultdict
            by_prod = defaultdict(list)
            for e in entries:
                by_prod[e['product'].id].append(e)

            commands = []
            for pid, group in by_prod.items():
                # Best cost is the minimum total cost
                best_cost = min(group, key=lambda g: g['total'])
                # Best lead time is the minimum lead time
                best_lead = min(group, key=lambda g: g['lead'])

                for g in group:
                    commands.append((0, 0, {
                        'product_id': pid,
                        'vendor_id': g['vendor'].id,
                        'unit_price': g['unit_price'],
                        'quantity': g['qty'],
                        'total_cost': g['total'],
                        'lead_time': g['lead'],
                        'currency_id': wiz.request_id.currency.id if wiz.request_id else False,
                        'is_best_cost': g is best_cost,
                        'is_best_lead': g is best_lead,
                        'is_dominated': any(
                            g['total'] >= o['total'] and g['lead'] >= o['lead'] and o is not g
                            for o in group
                        ),
                    }))
            wiz.summary_line_ids = commands

    # @api.depends('line_ids.vendor_unit_price', 'line_ids.quantity', 'line_ids.vendor_lead_time')
    # def _compute_summary_lines(self):
    #     for wiz in self:
    #         # Clear summary lines first
    #         wiz.summary_line_ids = [(5, 0, 0)]
    #
    #         # Do nothing with wiz.line_ids here!
    #         # Just build summary based on current line_ids data
    #
    #         entries = []
    #         for line in wiz.line_ids:
    #             total = (line.vendor_unit_price or 0.0) * (line.quantity or 0.0)
    #             entries.append({
    #                 'product': line.product_id,
    #                 'vendor': line.vendor_id,
    #                 'unit_price': line.vendor_unit_price,
    #                 'qty': line.quantity,
    #                 'total': total,
    #                 'lead': line.vendor_lead_time or 0,
    #             })
    #
    #         from collections import defaultdict
    #         by_prod = defaultdict(list)
    #         for e in entries:
    #             by_prod[e['product'].id].append(e)
    #
    #         commands = []
    #         for pid, group in by_prod.items():
    #             best_cost = min(group, key=lambda g: g['total'])
    #             best_lead = min(group, key=lambda g: g['lead'])
    #             for g in group:
    #                 commands.append((0, 0, {
    #                     'product_id': pid,
    #                     'vendor_id': g['vendor'].id,
    #                     'unit_price': g['unit_price'],
    #                     'quantity': g['qty'],
    #                     'total_cost': g['total'],
    #                     'lead_time': g['lead'],
    #                     'currency_id': wiz.request_id.currency.id if wiz.request_id else False,
    #                     'is_best_cost': g is best_cost,
    #                     'is_best_lead': g is best_lead,
    #                     'is_dominated': any(
    #                         g['total'] >= o['total'] and g['lead'] >= o['lead'] and o is not g
    #                         for o in group
    #                     ),
    #                 }))
    #         wiz.summary_line_ids = commands

    def action_confirm_purchase(self):
        for po in self.purchase_order_ids:
            if po.state in ['draft', 'sent']:  # Only confirm draft or RFQ purchase orders
                po.button_confirm()
        return {'type': 'ir.actions.act_window_close'}

    # def action_confirm_purchase(self):
    #     # Only keep checked lines
    #     vendor_map = {}
    #     for line in self.line_ids.filtered(lambda l: l.selected and l.quantity > 0):
    #         vendor_map.setdefault(line.vendor_id, []).append(line)
    #
    #     for vendor, lines in vendor_map.items():
    #         po_vals = {
    #             'partner_id': vendor.id,
    #             'order_line': [
    #                 (0, 0, {
    #                     'product_id': l.product_id.id,
    #                     'product_qty': l.quantity,
    #                     'product_uom': l.product_uom.id,
    #                     'price_unit': l.vendor_unit_price,
    #                     'name': l.product_id.display_name,
    #                     'date_planned': fields.Date.today(),
    #                 }) for l in lines
    #             ]
    #         }
    #         po = self.env['purchase.order'].create(po_vals)
    #         po.button_confirm()
    #     return {'type': 'ir.actions.act_window_close'}

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        purchase_order_ids = self.env.context.get('default_purchase_order_ids', [])
        res['purchase_order_ids'] = [(6, 0, purchase_order_ids)]

        lines = []
        existing_lines = set()  # Track product-vendor combos to avoid duplicates
        for po in self.env['purchase.order'].browse(purchase_order_ids):
            for ln in po.order_line:
                key = (ln.product_id.id, po.partner_id.id)
                if key in existing_lines:
                    continue  # skip duplicate
                existing_lines.add(key)
                lines.append((0, 0, {
                    'product_id': ln.product_id.id,
                    'vendor_id': po.partner_id.id,
                    'vendor_unit_price': ln.price_unit,
                    'quantity': ln.product_qty,
                    'vendor_lead_time': 0,
                    'selected': False,
                }))
        res['line_ids'] = lines
        return res

    # @api.model
    # def default_get(self, fields_list):
    #     res = super().default_get(fields_list)
    #     order_ids = self.env.context.get('default_order_ids')
    #     if not order_ids:
    #         return res
    #     # assign the orders to the wizard
    #     res['order_ids'] = [(6, 0, order_ids)]
    #     # Build one vendor-line per (order_line, vendor)
    #     lines = []
    #     orders = self.env['purchase.order'].browse(order_ids)
    #     for po in orders:
    #         for pol in po.order_line:
    #             for vinfo in pol.product_id.seller_ids:
    #                 lines.append((0, 0, {
    #                     'vendor_id': vinfo.partner_id.id,
    #                     'product_id': pol.product_id.id,
    #                     'product_uom': pol.product_uom.id,
    #                     'quantity': pol.product_qty,
    #                     'selected': False,
    #                 }))
    #     res['line_ids'] = lines
    #     return res

    def action_confirm_purchase(self):
        vendor_lines = {}
        # Only keep checked lines with positive qty
        for line in self.line_ids.filtered(lambda l: l.selected and l.quantity > 0):
            vendor_lines.setdefault(line.vendor_id, []).append(line)

        for vendor, lines in vendor_lines.items():
            # 1) Create the PO in draft
            po = self.env['purchase.order'].create({
                'partner_id': vendor.id,
                'order_line': [
                    (0, 0, {
                        'product_id': l.product_id.id,
                        'product_qty': l.quantity,
                        'product_uom': l.product_uom.id,
                        'price_unit': l.product_id.lst_price,
                        'name': l.product_id.name,
                        'date_planned': fields.Date.today(),
                    }) for l in lines
                ]
            })
            # 2) Confirm it to switch it to “Purchase Order”
            po.button_confirm()


class VendorPurchaseWizardLine(models.TransientModel):
    _name = 'vendor.purchase.wizard.line'
    _description = 'Vendor Purchase Wizard Line'

    wizard_id = fields.Many2one('vendor.purchase.wizard', ondelete='cascade')
    selected = fields.Boolean(string="Select", default=False)
    vendor_id = fields.Many2one('res.partner', string='Vendor', required=True)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_uom = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        compute='_compute_product_uom',
        store=True)

    # … other fields …

    @api.depends('product_id')
    def _compute_product_uom(self):
        for rec in self:
            # If no product, clear; otherwise use product.uom_id
            rec.product_uom = rec.product_id.uom_id.id or False

    quantity = fields.Float(string='Quantity', required=True)

    # User will enter this manually:
    vendor_unit_price = fields.Monetary(
        string='Unit Price',
        currency_field='vendor_currency_id',
        required=True)

    # Lead time can be manual or removed if not needed:
    vendor_lead_time = fields.Integer(string='Lead Time (days)')

    total_cost = fields.Monetary(
        string='Total Cost',
        currency_field='vendor_currency_id',
        compute='_compute_total_cost', store=True)

    vendor_currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id.id)

    @api.depends('vendor_unit_price', 'quantity')
    def _compute_total_cost(self):
        for line in self:
            line.total_cost = (line.vendor_unit_price or 0.0) * (line.quantity or 0.0)


class VendorPurchaseSummaryLine(models.TransientModel):
    _name = 'vendor.purchase.wizard.summary.line'
    _description = 'Vendor Purchase Summary Line'

    wizard_id = fields.Many2one(
        'vendor.purchase.wizard',
        ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string='Product', readonly=True)
    vendor_id = fields.Many2one(
        'res.partner', string='Vendor', readonly=True)
    unit_price = fields.Monetary(
        string='Unit Price',
        currency_field='currency_id',
        readonly=True)
    quantity = fields.Float(
        string='Qty', readonly=True)
    total_cost = fields.Monetary(
        string='Total Cost',
        currency_field='currency_id',
        readonly=True)
    lead_time = fields.Integer(
        string='Lead Time (days)', readonly=True)

    is_best_cost = fields.Boolean(
        string='Best Cost', readonly=True)
    is_best_lead = fields.Boolean(
        string='Best Lead', readonly=True)
    is_dominated = fields.Boolean(
        string='Dominated', readonly=True)

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency', readonly=True)
