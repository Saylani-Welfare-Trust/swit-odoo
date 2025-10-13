from odoo import models, fields, api
from odoo.tools.translate import _
import base64


class custom_purchase_request(models.Model):
    _name = 'custom.purchase.request'
    _description = 'custom purchase request'
    _rec_name = 'purchase_order_no'

    purchase_order_no = fields.Char(
        string='Purchase',
        required=False)


    currency = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id.id,
        required=False)

    order_deadline = fields.Datetime(
        string='Order Deadline',
        required=False)

    expected_arrival = fields.Datetime(
        string='Expected Arrival',
        required=False)

    deliver_to = fields.Many2one(
        comodel_name='stock.picking.type',
        string='Deliver To',
        required=False)

    line_ids = fields.One2many(
        comodel_name='custom.purchase.request_lines',
        inverse_name='line_id',
        string='Line_ids',
        required=False)

    def action_open_vendor_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vendor-wise Purchase',
            'view_mode': 'form',
            'res_model': 'vendor.purchase.wizard',
            'target': 'new',
            'context': {
                'default_request_id': self.id
            }
        }

    def action_send_email_to_vendors(self):
        Mail = self.env['mail.mail']
        xmlid = 'custom_purchase_request.purchase_req_quo_report_action'
        for request in self:
            vendor_map = {}
            for line in request.line_ids:
                for vendor in line.vendor:
                    vendor_map.setdefault(vendor, []).append(line)

            for vendor, lines in vendor_map.items():
                if not vendor.email:
                    continue

                # CORRECT call: xmlid first, then [ids], then data
                pdf_bytes, _ = self.env['ir.actions.report']._render_qweb_pdf(
                    xmlid,
                    [request.id],
                    {'vendor_id': vendor.id}
                )
                datas = base64.b64encode(pdf_bytes)

                mail_vals = {
                    'subject': f"RFQ: {request.purchase_order_no}",
                    'body_html': f"<p>Dear {vendor.name},</p><p>Find attached our Request for Quotation.</p>",
                    'email_to': vendor.email,
                    'auto_delete': True,
                    'attachment_ids': [(0, 0, {
                        'name': f"{request.purchase_order_no}_{vendor.name}.pdf",
                        'type': 'binary',
                        'datas': datas,
                        'mimetype': 'application/pdf',
                        'res_model': 'mail.mail',
                    })],
                }
                Mail.create(mail_vals).send()
        return True

    def action_send_email_to_vendors33(self):
        Mail = self.env['mail.mail']
        report_xml_id = ('custom_purchase_request.'
                         'purchase_req_quo_report_action')  # Ensure this is the correct XML ID
        for request in self:
            vendor_map = {}
            for line in request.line_ids:
                for vendor in line.vendor:
                    vendor_map.setdefault(vendor, []).append(line)

            for vendor, lines in vendor_map.items():
                if not vendor.email:
                    continue
                pdf_bytes, _ = self.env['ir.actions.report']._render_qweb_pdf(
                    report_xml_id,
                    [request.id],  # Document IDs
                    data={'vendor_id': vendor.id}  # Explicit data
                )
                datas = base64.b64encode(pdf_bytes)
                mail_vals = {
                    'subject': f"RFQ: {request.purchase_order_no}",
                    'body_html': f"<p>Dear {vendor.name},</p><p>Find attached our Request for Quotation.</p>",
                    'email_to': vendor.email,
                    'auto_delete': True,
                    'attachment_ids': [(0, 0, {
                        'name': f"{request.purchase_order_no}.pdf",
                        'type': 'binary',
                        'datas': datas,
                        'mimetype': 'application/pdf',
                        'res_model': 'mail.mail',
                    })],
                }
                Mail.create(mail_vals).send()
        return True

    @api.model
    def create(self, vals):
        if 'purchase_order_no' not in vals or not vals['purchase_order_no']:
            # Generate the sequence number for mis_no
            vals['purchase_order_no'] = self.env['ir.sequence'].next_by_code('pr.number') or 'New'
        return super(custom_purchase_request, self).create(vals)


class custom_purchase_request_lines(models.Model):
    _name = 'custom.purchase.request_lines'
    _description = 'custom purchase request_lines'

    line_id = fields.Many2one(
        comodel_name='custom.purchase.request',
        string='Line_id',
        required=False)

    product = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        required=False
    )

    name = fields.Text(
        string="Description",
        required=False
    )

    product_qty = fields.Float(
        string='Quantity',
        required=False,
        default=1.0
    )

    vendor = fields.Many2many(
        comodel_name='res.partner',
        string='Vendor'
    )

    product_uom = fields.Many2one(
        comodel_name='uom.uom',
        string='UoM',
        required=False
    )

    price_unit = fields.Float(
        string='Price Unit',
        required=False
    )

    taxes_id = fields.Many2many(
        comodel_name='account.tax',
        string='Taxes'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id.id
    )

    tax_excl = fields.Monetary(
        string='Tax Excluded Amount',
        currency_field='currency_id',
        compute='_compute_tax_excl',
        store=True
    )

    # Auto-fill fields based on product selection
    @api.onchange('product')
    def _onchange_product(self):
        if self.product:
            self.name = self.product.name
            self.product_uom = self.product.uom_id
            self.price_unit = self.product.lst_price
            self.taxes_id = self.product.taxes_id
            self.currency_id = self.env.company.currency_id

    # Calculate the tax-excluded amount
    @api.depends('price_unit', 'product_qty')
    def _compute_tax_excl(self):
        for record in self:
            record.tax_excl = record.price_unit * record.product_qty if record.price_unit and record.product_qty else 0.0




