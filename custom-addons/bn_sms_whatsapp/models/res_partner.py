from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    whatsapp = fields.Char(string="WhatsApp")

    @api.onchange('mobile')
    def _onchange_mobile(self):
        """Auto copy mobile number to whatsapp field (UI form use)"""
        if self.mobile:
            self.whatsapp = self.mobile

    @api.model_create_multi
    def create(self, vals_list):
        """Auto copy mobile to whatsapp when partner is created
        from anywhere, including POS"""
        for vals in vals_list:
            if vals.get('mobile') and not vals.get('whatsapp'):
                vals['whatsapp'] = vals['mobile']
        return super().create(vals_list)

    def write(self, vals):
        """Keep whatsapp in sync if mobile is updated later"""
        if vals.get('mobile') and not vals.get('whatsapp'):
            vals['whatsapp'] = vals['mobile']
        return super().write(vals)