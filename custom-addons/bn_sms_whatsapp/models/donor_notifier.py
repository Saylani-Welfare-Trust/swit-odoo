import base64
import logging
import threading

from odoo import SUPERUSER_ID, _, api, models

_logger = logging.getLogger(__name__)


class DonorNotifier(models.AbstractModel):
    """Donation receipt to the donor, used by every donation flow (POS order,
    direct deposit, imported / online donation, donation in kind ...).

    WhatsApp comes first: the PDF receipt on the donor's WhatsApp number.
    SMS is the fallback, only when the donor has no WhatsApp number or the
    WhatsApp message could not be sent, so a donor gets one message, not two.
    The SMS carries the receipt link when the receipt could be generated.
    Each attempt is logged on the donation's chatter."""
    _name = 'donor.notifier'
    _description = 'Donation receipt: WhatsApp first, SMS fallback'

    @api.model
    def _receipt_url(self, record, report_name, filename):
        """Render ``report_name`` for ``record`` (one receipt for all of them when
        several records make one donation), attach it to the first one and return
        a link with an access token (the attachment itself is not public)."""
        pdf_data, _type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(report_name, record.ids)
        record = record[:1]
        if not pdf_data or not pdf_data.startswith(b'%PDF'):
            raise Exception("Invalid PDF generated")
        if getattr(threading.current_thread(), 'testing', False):
            attachment = self._attach_receipt(self.env, record, filename, pdf_data)
        else:
            # WhatsApp downloads the PDF from the link straight away, before this
            # request commits: the attachment is saved in its own transaction so
            # the link already works when the provider opens it.
            with self.env.registry.cursor() as cr:
                attachment = self._attach_receipt(api.Environment(cr, SUPERUSER_ID, {}), record, filename, pdf_data)
        # Earlier copies of this receipt are removed here, in this request's own
        # transaction (removing them in the other one could wait on this one).
        self.env['ir.attachment'].sudo().search([
            ('res_model', '=', record._name), ('res_id', '=', record.id),
            ('name', '=', filename), ('id', '!=', attachment['id']),
        ]).unlink()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/web/content/{attachment['id']}?access_token={attachment['access_token']}&download=true"

    @api.model
    def _attach_receipt(self, env, record, filename, pdf_data):
        attachment = env['ir.attachment'].sudo().create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_data),
            'res_model': record._name,
            'res_id': record.id,
            'mimetype': 'application/pdf',
        })
        attachment.generate_access_token()
        return {'id': attachment.id, 'access_token': attachment.access_token}

    @api.model
    def _send(self, record, partner, sms_message, report_name=None, filename=None):
        """Send the receipt of ``record`` to ``partner``.

        ``sms_message`` is a callable taking the receipt link (or None) and
        returning the SMS text. Returns {'status', 'channel', 'message'}:
        status 'success' (sent by the expected channel), 'warning' (sent by
        SMS because WhatsApp failed) or 'error' (nothing sent)."""
        if not partner:
            return self._log(record, 'error', None, _('Donation receipt not sent: no donor.'))
        label = ', '.join(name or str(rec.id) for rec, name in zip(record, record.mapped('display_name')))
        filename = filename or 'Receipt_%s.pdf' % (record[:1].display_name or record[:1].id).replace('/', '_')
        url, url_error = None, None

        def receipt():
            nonlocal url, url_error
            if url is None and url_error is None and report_name:
                try:
                    url = self._receipt_url(record, report_name, filename)
                except Exception as e:  # noqa: BLE001 - the message still goes out by SMS
                    url_error = str(e)
                    _logger.error('%s: receipt PDF failed: %s', label, url_error)
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
                _logger.error('%s: WhatsApp failed: %s', label, whatsapp_error)

        mobile = partner.mobile or partner.phone or whatsapp
        if not mobile:
            return self._log(record, 'error', None,
                             _('Donation receipt not sent: the donor has no WhatsApp or mobile number.'))
        try:
            self.env['sms.service'].send_sms(mobile, sms_message(receipt()))
        except Exception as e:  # noqa: BLE001
            _logger.error('%s: SMS failed: %s', label, e)
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
        for rec in record:
            if not hasattr(rec, 'message_post'):
                continue
            try:
                with self.env.cr.savepoint():
                    rec.sudo().message_post(body=message)
            except Exception as e:  # noqa: BLE001 - logging must not stop the flow
                _logger.warning('%s: could not log the receipt message: %s', rec.display_name, e)
        return {'status': status, 'channel': channel, 'message': message}
