import requests
import logging
from odoo import models

_logger = logging.getLogger(__name__)

# System parameters (Settings > Technical > System Parameters)
PARAM_PREFIX = 'bn_sms_whatsapp.'
WHATSAPP_DEFAULTS = {
    'whatsapp_url': 'https://wa-bsp.contegris.com/v3/whatsApp/sendTemplateMessage',
    'whatsapp_template': 'oddo_receipt',
    'whatsapp_namespace': 'e8ae951d_c2e0_4b3a_b304_a4f7c4893315',
}


class WhatsAppService(models.Model):
    _name = 'whatsapp.service'
    _description = 'WhatsApp Service'

    def _get_param(self, key, required=True):
        value = self.env['ir.config_parameter'].sudo().get_param(PARAM_PREFIX + key) or WHATSAPP_DEFAULTS.get(key)
        if required and not value:
            raise Exception("System parameter %s%s is not set." % (PARAM_PREFIX, key))
        return value

    def format_number(self, mobile):
        mobile = ''.join(filter(str.isdigit, str(mobile)))

        if mobile.startswith('0'):
            mobile = mobile[1:]
        if mobile.startswith('92'):
            mobile = mobile[2:]

        return '92' + mobile

    def send_template_message(self, mobile, document_link, filename):
        formatted_mobile = self.format_number(mobile)

        # the API token and sender number are credentials: kept out of the code
        token = self._get_param('whatsapp_token')
        sender = self._get_param('whatsapp_from')

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {
            "from": sender,
            "number": sender,
            "toNumber": formatted_mobile,
            "messageType": "template",
            "name": self._get_param('whatsapp_template'),
            "language": "en",
            "namespace": self._get_param('whatsapp_namespace'),
            "header": {
                "parameters": [
                    {
                        "type": "document",
                        "document": {
                            "link": document_link,
                            "fileName": filename
                        }
                    }
                ]
            }
        }

        _logger.info("Sending WhatsApp to: %s", formatted_mobile)

        response = requests.post(self._get_param('whatsapp_url'), headers=headers, json=payload, timeout=30)

        if response.status_code != 200:
            _logger.error("WhatsApp API Error: %s", response.text)
            raise Exception(response.text)

        _logger.info("WhatsApp sent successfully")
        return True
