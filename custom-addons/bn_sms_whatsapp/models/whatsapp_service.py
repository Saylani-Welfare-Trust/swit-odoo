import requests
import logging
from odoo import models

_logger = logging.getLogger(__name__)

# Settings of the template messages (send_text_template / send_document_template),
# from the Development branch: System Parameters (Settings > Technical >
# System Parameters) bn_sms_whatsapp.<key> when set, else these defaults.
PARAM_PREFIX = 'bn_sms_whatsapp.'
WHATSAPP_DEFAULTS = {
    'whatsapp_url': 'https://wa-bsp.contegris.com/v3/whatsApp/sendTemplateMessage',
    'whatsapp_template': 'oddo_receipt',
    'whatsapp_namespace': 'e8ae951d_c2e0_4b3a_b304_a4f7c4893315',
}

class WhatsAppService(models.Model):
    _name = 'whatsapp.service'
    _description = 'WhatsApp Service'

    def format_number(self, mobile):
        mobile = ''.join(filter(str.isdigit, str(mobile)))

        if mobile.startswith('0'):
            mobile = mobile[1:]
        if mobile.startswith('92'):
            mobile = mobile[2:]

        return '92' + mobile

    def send_template_message(self, mobile, document_link, filename):
        formatted_mobile = self.format_number(mobile)

        url = "https://wa-bsp.contegris.com/v3/whatsApp/sendTemplateMessage"
        
        token = "1cef8d8cae4f4ed0c3e060ee1b56f3547cf314fd7a347851da97eded440404a5f30288b174bf6ebdcaae454d2ab116df7b83b91238d6d601b6eaffecf2be6149fb71b3d3f4eb2083a4109dfdde7c75fc4639b9acf33d71173a21d310f69f16d559a8a3ed061a0ae8b897172f31d8989980c3138447bad13fc3f4f1dbb59a1c6e5d5b2260776bfd6e11c69990578e9805c110c487bb4f9cd11e29cba7332b14b6d88ed602c3e449eb7d24c1ebbd401f1a10b9005a8c963f73c14992cb9e2e4f09"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {
            "from": "923111729526",
            "number": "923111729526",
            "toNumber": formatted_mobile,
            "messageType": "template",
            "name": "oddo_receipt",
            "language": "en",
            "namespace": "e8ae951d_c2e0_4b3a_b304_a4f7c4893315",
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
        _logger.info("Document URL: %s", document_link)

        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code != 200:
            _logger.error("WhatsApp API Error: %s", response.text)
            raise Exception(response.text)

        _logger.info("WhatsApp sent successfully")
        return True


    # ------------------------------------------------------------------
    # Template messages with a document header or text parameters (used by
    # Sadqa e Jariya). The receipt message above is unchanged.
    # ------------------------------------------------------------------
    def _get_param(self, key, required=True):
        value = self.env['ir.config_parameter'].sudo().get_param(PARAM_PREFIX + key) or WHATSAPP_DEFAULTS.get(key)
        if required and not value:
            raise Exception("System parameter %s%s is not set." % (PARAM_PREFIX, key))
        return value

    def _post_template(self, payload):
        """Token and sender: System Parameters bn_sms_whatsapp.whatsapp_token /
        whatsapp_from when set, else the ones of the receipt message."""
        token = self._get_param('whatsapp_token', required=False) or self._receipt_credentials()[0]
        sender = self._get_param('whatsapp_from', required=False) or self._receipt_credentials()[1]
        payload = dict(payload, **{"from": sender, "number": sender})
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        response = requests.post(self._get_param('whatsapp_url'), headers=headers, json=payload, timeout=30)
        if not response.ok:
            _logger.error("WhatsApp API Error: %s", response.text)
            raise Exception(response.text)
        # The provider can answer HTTP 200 with a rejection in the body
        try:
            result = response.json()
        except ValueError:
            result = None
        if isinstance(result, dict):
            status = str(result.get("status") or "").lower()
            error = result.get("error")
            if result.get("success") is False or error or status in {"error", "failed", "failure", "rejected"}:
                message = result.get("message") or error or result
                _logger.error("WhatsApp provider rejected the message: %s", message)
                raise Exception(str(message))
        _logger.info("WhatsApp provider accepted the message (HTTP %s)", response.status_code)
        return True

    def _receipt_credentials(self):
        """(token, sender) of send_template_message, read from its code so they stay in one place."""
        import inspect
        source = inspect.getsource(type(self).send_template_message)
        token = re.search(r'token\s*=\s*"([^"]+)"', source)
        sender = re.search(r'"from"\s*:\s*"([^"]+)"', source)
        return (token.group(1) if token else None, sender.group(1) if sender else None)

    def send_document_template(self, mobile, template_name, namespace, document_link, filename, language='en'):
        """Send an approved template with a Document header and a fixed body (no placeholders)"""
        payload = {
            "toNumber": self.format_number(mobile),
            "messageType": "template",
            "name": template_name,
            "language": language or "en",
            "namespace": namespace or self._get_param('whatsapp_namespace'),
            "header": {"parameters": [{"type": "document", "document": {"link": document_link, "fileName": filename}}]},
        }
        # the link is not logged, its access token opens the document
        _logger.info("Sending WhatsApp template %s to: %s", template_name, payload["toNumber"])
        return self._post_template(payload)

    def send_text_template(self, mobile, template_name, namespace, body_parameters, language='en'):
        """Send an approved template whose body has {{1}}, {{2}}, ... text placeholders"""
        payload = {
            "toNumber": self.format_number(mobile),
            "messageType": "template",
            "name": template_name,
            "language": language or "en",
            "namespace": namespace,
            "body": {"parameters": [{"type": "text", "text": str(value or '')} for value in body_parameters]},
        }
        # parameters are not logged, they may hold credentials
        _logger.info("Sending WhatsApp template %s to: %s", template_name, payload["toNumber"])
        return self._post_template(payload)
