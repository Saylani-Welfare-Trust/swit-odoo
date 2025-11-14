from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'


    microfinance_line_ids = fields.One2many('microfinance', 'donee_id', string='Microfinance Lines')