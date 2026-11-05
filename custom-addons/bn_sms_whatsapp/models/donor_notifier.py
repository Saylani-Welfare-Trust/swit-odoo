import base64
import logging

from odoo import _, api, models

_logger = logging.getLogger(__name__)


class DonorNotifier(models.AbstractModel):
    """Donation receipt to the donor, used by every donation flow (POS order,
    direct deposit, imported / online donation, donation in kind ...).

    WhatsApp comes first: the PDF receipt on the donor's WhatsApp number.
    SMS is the fallback, only when the donor has no WhatsApp number or the
    WhatsApp message could not be sent, so a donor gets one message, not two.
    The SMS carries the receipt link when the receipt could be generated.
    Each attempt is logged on the donation's chatter."""
    _name = 'bn.donor.notifier'
    _description = 'Donation receipt: WhatsApp first, SMS fallback'

    @api.model
    def _receipt_url(self, record, report_name, filename):
        """Render ``report_name`` for ``record``, attach it and return a link
        with an access token (the attachment itself is not public)."""
        pdf_data, _type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(report_name, [record.id])
        if not pdf_data or not pdf_data.startswith(b'%PDF'):
            raise Exception("Invalid PDF generated")
        Attachment = self.env['ir.attachment'].sudo()
        Attachment.search([('res_model', '=', record._name), ('res_id', '=', record.id),
                           ('name', '=', filename)]).unlink()
        attachment = Attachment.create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_data),
            'res_model': record._name,
            'res_id': record.id,
            'mimetype': 'application/pdf',
        })
        attachment.generate_access_token()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/web/content/{attachment.id}?access_token={attachment.access_token}&download=true"

    @api.model
    def _send(self, record, partner, sms_message, report_name=None, filename=None):
        """Send the receipt of ``record`` to ``partner``.

        ``sms_message`` is a callable taking the receipt link (or None) and
        returning the SMS text. Returns {'status', 'channel', 'message'}:
        status 'success' (sent by the expected channel), 'warning' (sent by
        SMS because WhatsApp failed) or 'error' (nothing sent)."""
        if not partner:
            return self._log(record, 'error', None, _('Donation receipt not sent: no donor.'))
        filename = filename or 'Receipt_%s.pdf' % (record.display_name or record.id).replace('/', '_')
        url, url_error = None, None

        def receipt():
            nonlocal url, url_error
            if url is None and url_error is None and report_name:
                try:
                    url = self._receipt_url(record, report_name, filename)
                except Exception as e:  # noqa: BLE001 - the message still goes out by SMS
                    url_error = str(e)
                    _logger.error('%s: receipt PDF failed: %s', record.display_name, url_error)
            return url

        whatsapp = partner.whatsapp if 'whatsapp' in partner._fields else False
        whatsapp_error = None
        if whatsapp:
            try:
                link = receipt()
                if not link:
                    raise Exception(url_error or 'no receipt to send')
                self.env['whatsapp.service'].send_template_message(whatsapp, link, filename)
                return self._log(record, 'success', 'whatsapp',
                                 _('Donation receipt sent by WhatsApp to %s.', whatsapp))
            except Exception as e:  # noqa: BLE001 - fall back to SMS
                whatsapp_error = str(e)
                _logger.error('%s: WhatsApp failed: %s', record.display_name, whatsapp_error)

        mobile = partner.mobile or partner.phone or whatsapp
        if not mobile:
            return self._log(record, 'error', None,
                             _('Donation receipt not sent: the donor has no WhatsApp or mobile number.'))
        try:
            self.env['sms.service'].send_sms(mobile, sms_message(receipt()))
        except Exception as e:  # noqa: BLE001
            _logger.error('%s: SMS failed: %s', record.display_name, e)
            reason = _('WhatsApp failed: %s. ', whatsapp_error) if whatsapp else ''
            return self._log(record, 'error', None,
                             _('Donation receipt not sent. %sSMS failed: %s', reason, e))
        if whatsapp:
            return self._log(record, 'warning', 'sms',
                             _('Donation receipt sent by SMS to %s (WhatsApp failed: %s).', mobile, whatsapp_error))
        return self._log(record, 'success', 'sms',
                         _('Donation receipt sent by SMS to %s (no WhatsApp number).', mobile))

    @api.model
    def _log(self, record, status, channel, message):
        if hasattr(record, 'message_post'):
            try:
                with self.env.cr.savepoint():
                    record.sudo().message_post(body=message)
            except Exception as e:  # noqa: BLE001 - logging must not stop the flow
                _logger.warning('%s: could not log the receipt message: %s', record.display_name, e)
        return {'status': status, 'channel': channel, 'message': message}
