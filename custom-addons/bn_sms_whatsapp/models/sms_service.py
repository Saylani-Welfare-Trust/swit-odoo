import requests
from odoo import models

class SmsService(models.Model):
    _name = 'sms.service'
    _description = 'SMS Service'


    def send_sms(self, mobile, message):
        url = "https://bsms.telecard.com.pk/SMSportal/Customer/apikey.aspx"
        api_key = "b523c2a5acb9472db394379889fd9336"

        params = {
            "apikey": api_key,
            "msg": message,
            "mobileno": mobile
        }

        response = requests.get(url, params=params)

        if response.status_code != 200:
            raise Exception(response.text)

        return True