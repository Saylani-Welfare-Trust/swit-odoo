import requests
import logging
from odoo import models

_logger = logging.getLogger(__name__)

API_URL = "https://wa-bsp.contegris.com/v3/whatsApp/sendTemplateMessage"
API_TOKEN = "1cef8d8cae4f4ed0c3e060ee1b56f3547cf314fd7a347851da97eded440404a5f30288b174bf6ebdcaae454d2ab116df7b83b91238d6d601b6eaffecf2be6149fb71b3d3f4eb2083a4109dfdde7c75fc4639b9acf33d71173a21d310f69f16d559a8a3ed061a0ae8b897172f31d8989980c3138447bad13fc3f4f1dbb59a1c6e5d5b2260776bfd6e11c69990578e9805c110c487bb4f9cd11e29cba7332b14b6d88ed602c3e449eb7d24c1ebbd401f1a10b9005a8c963f73c14992cb9e2e4f09"
SENDER_NUMBER = "923111729526"
# namespace of the WhatsApp Business account, shared by its approved templates
NAMESPACE = "e8ae951d_c2e0_4b3a_b304_a4f7c4893315"

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

    def _post_template(self, payload):
        headers = {
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json"
        }

        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)

        if response.status_code != 200:
            _logger.error("WhatsApp API Error: %s", response.text)
            raise Exception(response.text)

        _logger.info("WhatsApp sent successfully")
        return True

    def send_template_message(self, mobile, document_link, filename):
        formatted_mobile = self.format_number(mobile)

        payload = {
            "from": SENDER_NUMBER,
            "number": SENDER_NUMBER,
            "toNumber": formatted_mobile,
            "messageType": "template",
            "name": "oddo_receipt",
            "language": "en",
            "namespace": NAMESPACE,
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

        return self._post_template(payload)

    def send_document_template(self, mobile, template_name, namespace, document_link, filename, language='en'):
        """Send an approved template with a Document header and a fixed body (no placeholders)"""
        formatted_mobile = self.format_number(mobile)

        payload = {
            "from": SENDER_NUMBER,
            "number": SENDER_NUMBER,
            "toNumber": formatted_mobile,
            "messageType": "template",
            "name": template_name,
            "language": language or "en",
            "namespace": namespace or NAMESPACE,
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

        # the link is not logged, its access token opens the document
        _logger.info("Sending WhatsApp template %s to: %s", template_name, formatted_mobile)

        return self._post_template(payload)

    def send_text_template(self, mobile, template_name, namespace, body_parameters, language='en'):
        """Send an approved template whose body has {{1}}, {{2}}, ... text placeholders"""
        formatted_mobile = self.format_number(mobile)

        payload = {
            "from": SENDER_NUMBER,
            "number": SENDER_NUMBER,
            "toNumber": formatted_mobile,
            "messageType": "template",
            "name": template_name,
            "language": language or "en",
            "namespace": namespace,
            "body": {
                "parameters": [
                    {"type": "text", "text": str(value or '')}
                    for value in body_parameters
                ]
            }
        }

        # parameters are not logged, they may hold credentials
        _logger.info("Sending WhatsApp template %s to: %s", template_name, formatted_mobile)

        return self._post_template(payload)
