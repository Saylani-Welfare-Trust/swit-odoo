from odoo import models, fields


class LiveStockVariant(models.Model):
    _name = 'livestock.variant'
    _description = 'Livestock Variant'

    name = fields.Char(
        string='Name',
        required=False
    )
