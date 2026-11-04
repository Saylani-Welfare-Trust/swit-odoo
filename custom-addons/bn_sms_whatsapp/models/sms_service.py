import requests
from odoo import models

SMS_URL = "https://bsms.telecard.com.pk/SMSportal/Customer/apikey.aspx"


class SmsService(models.Model):
    _name = 'sms.service'
    _description = 'SMS Service'

    def send_sms(self, mobile, message):
        # System parameter: the API key is a credential, kept out of the code
        params_model = self.env['ir.config_parameter'].sudo()
        api_key = params_model.get_param('bn_sms_whatsapp.sms_api_key')
        if not api_key:
            raise Exception("System parameter bn_sms_whatsapp.sms_api_key is not set.")

        params = {
            "apikey": api_key,
            "msg": message,
            "mobileno": mobile
        }

        response = requests.get(params_model.get_param('bn_sms_whatsapp.sms_url') or SMS_URL, params=params, timeout=30)

        if response.status_code != 200:
            raise Exception(response.text)

        return True
