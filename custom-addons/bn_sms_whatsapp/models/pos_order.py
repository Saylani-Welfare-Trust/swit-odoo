from odoo import models, api
from odoo.exceptions import UserError
import base64
import logging

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model  
    def sms_or_whatsapp_send_receipt(self, order_id):
        _logger.info('WHATSAPP: whatsapp_send_receipt called')
        return self.send_whatsapp_after_payment(order_id)

    def send_whatsapp_after_payment(self, order_id):
        if isinstance(order_id, list):
            order_id = order_id[0] if order_id else None

        order = self.browse(int(order_id)) if order_id else None

        if not order:
            return {'status': 'error', 'message': 'Order not found'}

        if not order.partner_id:
            return {'status': 'error', 'message': 'No customer selected'}

        sms_message = ""
        pdf_url = ""

        try:
            _logger.info("Processing order: %s", order.name)

            # ---------------------------------
            # Generate PDF
            # ---------------------------------
            pdf_data = self._generate_pdf_from_report(order)

            if not pdf_data or not pdf_data.startswith(b'%PDF'):
                raise Exception("Invalid PDF generated")

            # ---------------------------------
            # Save attachment and generate URL
            # ---------------------------------
            attachment, pdf_url = self._save_as_attachment(order, pdf_data)

            _logger.info("PDF URL: %s", pdf_url)

            # ---------------------------------
            # SMS Message
            # ---------------------------------
            sms_message = (
                f"Thank you for donation of Rs. {order.amount_total}. "
                f"{order.user_id.branch_code}-"
                f"{order.date_order.year if order.date_order else ''}-"
                f"{order.pos_order_seq}\n\n"
                "Your generosity.\n"
                "Your donation will make an immediate difference in the lives of needy families.\n\n"
                f"Receipt: {pdf_url}"
            )

            # ---------------------------------
            # WhatsApp
            # ---------------------------------
            if not order.partner_id.whatsapp:
                raise Exception("Customer does not have a WhatsApp number.")

            self.env['whatsapp.service'].send_template_message(
                order.partner_id.whatsapp,
                pdf_url,
                "Donation Receipt.pdf"
            )

            _logger.info("WhatsApp sent successfully")

            return {
                'status': 'success',
                'message': 'WhatsApp sent successfully'
            }

        except Exception as e:
            _logger.exception("WhatsApp sending failed")

            # ---------------------------------
            # SMS Fallback
            # ---------------------------------
            mobile = order.partner_id.mobile or order.partner_id.phone

            if mobile:
                try:
                    self.env['sms.service'].send_sms(mobile, sms_message)

                    return {
                        'status': 'warning',
                        'message': f'WhatsApp failed ({str(e)}). SMS sent successfully.'
                    }

                except Exception as sms_error:
                    raise UserError(
                        f"WhatsApp failed: {str(e)}\n"
                        f"SMS also failed: {str(sms_error)}"
                    )

            raise UserError(
                f"WhatsApp failed: {str(e)}\n"
                "Customer has no mobile number for SMS fallback."
            )

    # -----------------------------------
    # Generate PDF
    # -----------------------------------
    def _generate_pdf_from_report(self, order):
        try:
            pdf_data, _ = self.env['ir.actions.report']._render_qweb_pdf(
                'bn_pos_order.pos_whatsapp_donation_receipt_template',
                [order.id]
            )
            _logger.info('PDF generated: %s bytes', len(pdf_data))
            return pdf_data

        except Exception as e:
            _logger.error('PDF error: %s', str(e))
            return None

    # -----------------------------------
    # Save Attachment + Generate URL
    # -----------------------------------

    
    def _save_as_attachment(self, order, pdf_data):
        # safe_name = order.name.replace('/', '_')
        filename = f"Donation Receipt.pdf"

        # Delete old
        old = self.env['ir.attachment'].search([
            ('res_model', '=', 'pos.order'),
            ('res_id', '=', order.id),
            ('name', '=', filename)
        ])
        old.unlink()

        # Create new
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_data),
            'res_model': 'pos.order',
            'res_id': order.id,
            'mimetype': 'application/pdf',
            'public': True,
        })

        # Generate access token
        attachment.generate_access_token()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        # ✅ FINAL WORKING URL
        pdf_url = (
            f"{base_url}/web/content/{attachment.id}/"
            f"Donation%20Receipt.pdf?access_token={attachment.access_token}&download=true"
        )
        return attachment, pdf_url