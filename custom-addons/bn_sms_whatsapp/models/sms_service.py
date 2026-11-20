import requests
from odoo import models

SMS_URL = "https://bsms.telecard.com.pk/SMSportal/Customer/apikey.aspx"
# Telecard key, as in the code before 18 Nov 26; the System Parameter bn_sms_whatsapp.sms_api_key overrides it
SMS_API_KEY = "b523c2a5acb9472db394379889fd9336"


class SmsService(models.Model):
    _name = 'sms.service'
    _description = 'SMS Service'

    def _api_key(self):
        return self.env['ir.config_parameter'].sudo().get_param('bn_sms_whatsapp.sms_api_key') or SMS_API_KEY

    def send_sms(self, mobile, message):
        params_model = self.env['ir.config_parameter'].sudo()
        api_key = self._api_key()
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
