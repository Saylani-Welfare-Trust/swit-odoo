
from odoo import models, fields, api
from odoo.exceptions import UserError  # <-- Ye import karna hai
import logging
class ResPartner(models.Model):
    _inherit = 'res.partner'


    whatsapp = fields.Char(string="WhatsApp")


    @api.model_create_multi
    def create(self, partner):
        """Auto copy mobile to whatsapp when partner is created
        from anywhere, including POS"""
        if partner.get('mobile'):
            partner['whatsapp'] = partner['mobile']
        
        return super().create(partner)
