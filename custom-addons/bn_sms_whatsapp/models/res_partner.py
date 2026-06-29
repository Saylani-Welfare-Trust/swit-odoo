from odoo import models, fields, api
from odoo.exceptions import UserError  
import logging

class ResPartner(models.Model):
    _inherit = 'res.partner'

    whatsapp = fields.Char(string="WhatsApp")

    @api.onchange('mobile')
    def _onchange_mobile(self):
        """Auto copy mobile number to whatsapp field"""
        if self.mobile:
            self.whatsapp = self.mobile