from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'


    is_microfinance = fields.Boolean(related='product_tmpl_id.is_microfinance', string="Is Microfinance", store=True, tracking=True)