from odoo import models, fields


class ProductCategory(models.Model):
    _inherit = 'product.category'

    is_meat = fields.Boolean(string="Is Meat Category")