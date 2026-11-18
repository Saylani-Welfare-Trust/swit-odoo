from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'


    whatsapp = fields.Char(string="WhatsApp")


    @api.model_create_multi
    def create(self, vals_list):
        """Auto copy mobile to whatsapp when partner is created
        from anywhere, including POS"""
        for vals in vals_list:
            if vals.get('mobile'):
                vals['whatsapp'] = vals['mobile']
        return super().create(vals_list)