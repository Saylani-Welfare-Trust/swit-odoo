from odoo import models, fields, api

class PosOrder(models.Model):
    _inherit = 'pos.order'

    is_microfinance_order = fields.Boolean('Is Microfinance Order?')


