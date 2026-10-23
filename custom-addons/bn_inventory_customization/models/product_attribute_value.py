from odoo import models, fields


class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    from_kg = fields.Float(string='From (kg)')
    to_kg = fields.Float(string='To (kg)')
