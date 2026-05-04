import requests
import json
import logging
from odoo import models

_logger = logging.getLogger(__name__)

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
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"WhatsApp API Error: {response.text}")

        return True