from odoo import models, api
import base64
import requests
import logging

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = 'pos.order'


    @api.model  
    def sms_or_whatsapp_send_receipt(self, order_id):
        """Send WhatsApp receipt - Called from JS"""
        return self.send_whatsapp_after_payment(order_id)

    def send_whatsapp_after_payment(self, order_id):
        """Called from JS after POS payment validation"""
        if isinstance(order_id, list):
            order_id = order_id[0] if order_id else None
        
        order = self.browse(int(order_id)) if order_id else None
        
        if not order:
            return {'status': 'error', 'message': 'Order not found'}
        
        if not order.partner_id:
            return {'status': 'error', 'message': 'No customer selected'}
        
        try:
            # SMS fallback message
            donation_items = ""
            for line in order.lines:
                donation_items += f"{line.qty} x {line.product_id.name} = {line.price_subtotal} PKR\n"
            
            sms_message = f"""Dear {order.partner_id.name},

Thank you for your donation!

Amount: {order.amount_total} PKR
Items:
{donation_items}

May Allah bless you!

- SWIT"""
            
            if order.partner_id.whatsapp:
                try:
                    # ✅ Custom slip se PDF generate karo
                    pdf_data = self._generate_pdf_from_report(order)
                    
                    if pdf_data and len(pdf_data) > 1000:
                        # ✅ Odoo attachment banao
                        attachment, pdf_url = self._save_as_attachment(order, pdf_data)
                        
                        # ✅ WhatsApp bhejo
                        whatsapp_service = self.env['whatsapp.service']
                        whatsapp_service.send_template_message(
                            order.partner_id.whatsapp,
                            pdf_url,
                            f"Receipt_{order.name}.pdf"
                        )
                        return {'status': 'success', 'message': 'WhatsApp sent'}
                    else:
                        raise Exception("PDF generation failed")
                        
                except Exception as e:
                    mobile = order.partner_id.mobile or order.partner_id.phone
                    if mobile:
                        self.env['sms.service'].send_sms(mobile, sms_message)
                        return {'status': 'success', 'message': 'SMS sent'}
            else:
                # WhatsApp nahi — SMS bhejo
                mobile = order.partner_id.mobile or order.partner_id.phone
                if mobile:
                    self.env['sms.service'].send_sms(mobile, sms_message)
                    
                    return {'status': 'success', 'message': 'SMS sent'}
                else:
                    return {'status': 'error', 'message': 'No contact number found'}
            
            
        except Exception as e:
            _logger.error('WHATSAPP Error: %s', str(e), exc_info=True)
            return {'status': 'error', 'message': str(e)}

    def _generate_pdf_from_report(self, order):
        try:
            report = self.env['ir.actions.report'].search([
                ('report_name', '=', 'bn_pos_order.pos_donation_receipt_template')
            ], limit=1)

            if not report:
                _logger.error('Report not found!')
                return None

            _logger.info('✅ Report found: %s', report.report_name)

            pdf_data, _ = self.env['ir.actions.report']._render_qweb_pdf(
                'bn_pos_order.pos_donation_receipt_template',
                [order.id]
            )

            _logger.info('✅ PDF generated: %s bytes', len(pdf_data))
            return pdf_data

        except Exception as e:
            _logger.error('Report error: %s', str(e))
            return None

    def _save_as_attachment(self, order, pdf_data):
        safe_name = order.name.replace('/', '_')
        filename = f"Receipt_{safe_name}.pdf"

        old = self.env['ir.attachment'].search([
            ('res_model', '=', 'pos.order'),
            ('res_id', '=', order.id),
            ('name', '=', filename)
        ])
        old.unlink()

        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_data).decode('utf-8'),
            'res_model': 'pos.order',
            'res_id': order.id,
            'mimetype': 'application/pdf',
            'public': True,
        })

        token_list = attachment.generate_access_token()
        access_token = token_list[0]

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        db_name = self.env.cr.dbname
        pdf_url = f"{base_url}/whatsapp/receipt/{attachment.id}?token={access_token}"
        _logger.info('PDF URL: %s', pdf_url)
        return attachment, pdf_url
