from odoo import models, fields, api,_
# from PyPDF2 import PdfMerger
import io
import base64
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    state = fields.Selection([
        ('draft', 'RFQ'),
        ('sent', ' RFQ Sent'),
        ('comparative', 'Comparative'),
        ('email', 'Email'),
        ('received', 'Received'),
        ('purchase', 'Purchase Order'),
        ('cancel', 'Cancel'),
        ('done','Lock'),
    ], default='draft', tracking=True, copy=False)

    order_milestone = fields.Char(string="Milestone")
    order_duration = fields.Float(string="duration")
    order_request_type = fields.Selection([
        ('trainers_teachers', 'Trainers / Teachers'),
        ('medical_practitioners', 'Medical practitioners’ services'),
        ('professional_consulting', 'Professional and Consulting'),
        ('repair_maintenance_general', 'Repair and Maintenance – General'),
        ('masajid_construction_repairs', 'Masajid Construction / Repairs'),
        ('madaris_construction_repairs', 'Madaris Construction / Repairs'),
        ('marketing', 'Marketing (including Digital marketing)'),
        ('contractual_employees_volunteers', 'Contractual employees / Volunteers'),
        ('insurance', 'Insurance'),
        ('rental_payments', 'Rental payments'),
        ('livestock_cutting_charges', 'Livestock cutting charges'),
        ('functions_events', 'Functions, Events'),
        ('it_services', 'IT Services'),
    ], string="Request Type")

    comparative_line_ids = fields.One2many(
        'purchase.comparative.line', 'comparative_id', string="Vendors"
    )

    received_line_ids = fields.One2many(
        'received.comparative.line', 'received_id', string="Received"
    )

    @api.depends('order_line', 'order_line.product_qty')
    @api.constrains('order_line', 'order_line.product_qty')
    def _compute_quantity(self):
        for rec in self:
            product_qty = []
            for line in rec.order_line:
                product_qty.append(line.product_qty)
            comparative_ids = self.env['purchase.comparative.line'].search([('po_id', '=', rec.id)])
            print(comparative_ids)
            for lines in comparative_ids:
                lines.write({
                    'quantity': sum(product_qty)
                })

    def button_confirm(self):
        for order in self:
            order.order_line._validate_analytic_distribution()
            order._add_supplier_to_product()
            if order._approval_allowed():
                order.button_approve()
                order.write({'state': 'purchase'})
            else:
                order.write({'state': 'purchase'})
            if order.partner_id not in order.message_partner_ids:
                order.message_subscribe([order.partner_id.id])

            for line in order.order_line:
                self.env['stock.quality.check'].create({
                    'product_id': line.product_id.id,
                    'quality_check': 'default',
                    'stock_picking_id': order.picking_ids.id if order.picking_ids else False
                })
        return True

    def create(self, vals):
        order = super(PurchaseOrder, self).create(vals)
        order._update_comparative_lines()
        return order

    def write(self, vals):
        result = super(PurchaseOrder, self).write(vals)
        for order in self:
            if not order.comparative_line_ids:
                order._update_comparative_lines()
        return result

    def _update_comparative_lines(self):
        for order in self:
            if order.partner_id:
                existing_vendor_ids = order.comparative_line_ids.mapped('vendor_id.id')
                if order.partner_id.id not in existing_vendor_ids:
                    self.env['purchase.comparative.line'].create({
                        'comparative_id': order.id,
                        'vendor_id': order.partner_id.id,
                        'product_ids': [(6, 0, order.order_line.mapped('product_id').ids)],
                        'quantity': sum(order.order_line.mapped('product_qty')),
                        'is_selected': False,
                    })

    # def action_comparative(self):
    #     for order in self:
    #         if len(order.comparative_line_ids) != 3:
    #             raise UserError("You must add exactly 3 vendors.")
    #
    #         vendor_ids = [line.vendor_id.id for line in order.comparative_line_ids]
    #         if len(vendor_ids) != len(set(vendor_ids)):
    #             raise UserError("You cannot select the same vendor multiple times.")
    #
    #         selected_lines = order.comparative_line_ids.filtered(lambda l: l.is_selected)
    #         if not selected_lines:
    #             raise UserError("Please select at least one vendor to proceed.")
    #
    #         purchase_orders = {}
    #         for line in selected_lines:
    #             if line.vendor_id.id not in purchase_orders:
    #                 new_po = self.env['purchase.order'].create({
    #                     'partner_id': line.vendor_id.id,
    #                     'order_line': []
    #                 })
    #                 purchase_orders[line.vendor_id.id] = new_po
    #
    #             if line.product_ids:
    #                 for product in line.product_ids:
    #
    #                     product_line = order.order_line.filtered(lambda l: l.product_id == product)
    #                     for pl in product_line:
    #                         self.env['purchase.order.line'].create({
    #                             'order_id': purchase_orders[line.vendor_id.id].id,
    #                             'product_id': pl.product_id.id,
    #                             'product_qty': pl.product_qty,
    #                             # 'price_unit': pl.price_unit,
    #                         })
    #
    #                     line.po_id = purchase_orders[line.vendor_id.id].id
    #
    #         order.state = 'comparative'
    def action_comparative(self):
        for order in self:
            if len(order.comparative_line_ids) != 2:
                raise UserError("You must add exactly 3 vendors.")

            vendor_ids = [line.vendor_id.id for line in order.comparative_line_ids]
            if len(vendor_ids) != len(set(vendor_ids)):
                raise UserError("You cannot select the same vendor multiple times.")

            selected_lines = order.comparative_line_ids.filtered(lambda l: l.is_selected)
            if not selected_lines:
                raise UserError("Please select at least one vendor to proceed.")

            purchase_orders = {}
            for line in selected_lines:
                if line.vendor_id.id not in purchase_orders:
                    new_po = self.env['purchase.order'].create({
                        'partner_id': line.vendor_id.id,
                        'order_line': [],
                        'state': 'sent',
                    })

                    purchase_orders[line.vendor_id.id] = new_po

                if line.product_ids:
                    for product in line.product_ids:
                        product_line = order.order_line.filtered(lambda l: l.product_id == product)
                        for pl in product_line:
                            self.env['purchase.order.line'].create({
                                'order_id': purchase_orders[line.vendor_id.id].id,
                                'product_id': pl.product_id.id,
                                'product_qty': pl.product_qty,
                            })

                line.po_id = purchase_orders[line.vendor_id.id].id

            # for po in purchase_orders.values():
            #     po.write({'state': 'sent'})

            order.state = 'comparative'

    # def action_received(self):
    #     for order in self:
    #         selected_lines = order.comparative_line_ids.filtered(lambda l: l.is_selected and l.po_id)
    #
    #         if not selected_lines:
    #             raise UserError("No selected vendors with generated POs found.")
    #
    #         received_lines = [(0, 0, {
    #             'vendor_id': line.vendor_id.id,
    #             'product_ids': line.product_ids.ids,
    #             'quantity': line.quantity,
    #             # 'price_unit': line.price_unit,
    #             'is_selected': line.is_selected,
    #             'po_id': line.po_id.id,
    #         }) for line in selected_lines]
    #
    #         order.write({'received_line_ids': received_lines})
    #
    #         order.state = 'received'
    def action_received(self):
        for order in self:
            selected_lines = order.comparative_line_ids.filtered(lambda l: l.is_selected and l.po_id)

            if not selected_lines:
                raise UserError("No selected vendors with generated POs found.")

            received_lines = []

            for line in selected_lines:
                price_unit = 0.0

                if line.po_id and line.product_ids:
                    for product in line.product_ids:
                        po_line = line.po_id.order_line.filtered(lambda l: l.product_id == product)
                        if po_line:
                            price_unit = po_line[0].price_unit
                            break

                received_lines.append((0, 0, {
                    'vendor_id': line.vendor_id.id,
                    'product_ids': line.product_ids.ids,
                    'quantity': line.quantity,
                    'price_unit': price_unit,
                    'is_selected': line.is_selected,
                    'po_id': line.po_id.id,
                }))

            order.write({'received_line_ids': received_lines})
            order.state = 'received'

    def print_quotation(self):
        result = super(PurchaseOrder, self).print_quotation()

        reports = []

        if self.partner_id:
            main_po_report = self.env.ref('purchase.report_purchase_quotation').report_action(self)
            reports.append(main_po_report)

        for line in self.comparative_line_ids:
            if line.vendor_id and line.product_ids:
                order_lines = []
                for product in line.product_ids:
                    purchase_order_line = self.env['purchase.order.line'].sudo().search([('order_id' ,'=', line.comparative_id.id), ('product_id' ,'=', product.id)])
                    if purchase_order_line:
                        for lines in purchase_order_line:
                            order_lines.append((0, 0, {
                                'product_id': lines.product_id.id,
                                'product_qty': lines.product_qty,
                                # 'price_unit': line.price_unit,
                            }))
                    else:
                        order_lines.append((0, 0, {
                            'product_id': product.id,
                            'product_qty': line.quantity,
                            # 'price_unit': line.price_unit,
                        }))

                new_po = self.env['purchase.order'].create({
                    'partner_id': line.vendor_id.id,
                    'order_line': order_lines,
                })

                report = self.env.ref('purchase.report_purchase_quotation').report_action(new_po)
                reports.append(report)

        if len(reports) > 0:
            try:
                combined_pdf = self._combine_pdfs(reports)

                attachment = self.env['ir.attachment'].create({
                    'name': f'Combined_PO_{self.name}.pdf',
                    'type': 'binary',
                    'datas': base64.b64encode(combined_pdf),
                    'res_model': 'purchase.order',
                    'res_id': self.id,
                    'mimetype': 'application/pdf',
                })

                return {
                    'type': 'ir.actions.act_url',
                    'url': f'/web/content/{attachment.id}?download=true',
                    'target': 'self',
                }
            except Exception as e:
                raise UserError(f"Failed to combine PDFs: {str(e)}")
        else:
            return result

    def _combine_pdfs(self, reports):
        merger = PdfMerger()
        try:
            for report in reports:
                pdf_content = self.env['ir.actions.report']._render_qweb_pdf(
                    report['report_name'], report['context']['active_ids']
                )
                merger.append(io.BytesIO(pdf_content[0]))

            combined_pdf = io.BytesIO()
            merger.write(combined_pdf)
            merger.close()

            return combined_pdf.getvalue()
        except Exception as e:
            raise UserError(f"Failed to generate or combine PDFs: {str(e)}")
        finally:
            merger.close()

    def action_send_vendor_email(self):
        mail_server = self.env['ir.mail_server'].sudo().search([], limit=1)
        if not mail_server:
            raise UserError('Mail server configuration is missing.')

        web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        for order in self:
            selected_lines = order.comparative_line_ids.filtered(lambda r: r.is_selected)

            if not selected_lines:
                raise UserError('No vendors selected for email notification.')

            for record in selected_lines:
                if not record.vendor_id.email:
                    raise UserError(f"No email address found for {record.vendor_id.name}.")

                link = "{}/web#id={}&view_type=form&model=purchase.order".format(
                    web_base_url, order.id
                )

                email_body = """
                    <p>Dear {vendor_name},</p>
                    <p>You have been selected as an alternative vendor for a purchase order.</p>
                    <p><strong>Order Reference:</strong> {order_name}</p>
                    <p>Please review the details and take necessary action.</p>
                    <a href="{link}" style="
                        display: inline-block;
                        padding: 10px 20px;
                        font-size: 14px;
                        font-weight: bold;
                        color: #fff;
                        background-color: #007bff;
                        text-decoration: none;
                        border-radius: 5px;
                        text-align: center;">
                        View Purchase Order
                    </a>
                    <p>Best Regards,</p>
                    <p>Team ERP</p>
                """.format(
                    vendor_name=record.vendor_id.name,
                    order_name=order.name,
                    link=link
                )

                mail_vals = {
                    'email_from': mail_server.smtp_user,
                    'email_to': record.vendor_id.email,
                    'subject': 'Alternative Vendor Notification - Purchase Order: %s' % order.name,
                    'body_html': email_body,
                }
                mail_id = self.env['mail.mail'].sudo().create(mail_vals)
                mail_id.send()

            order.state = 'email'

        return True

