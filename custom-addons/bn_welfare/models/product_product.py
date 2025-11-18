from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'


    is_welfare = fields.Boolean(related='product_tmpl_id.is_microfinance', string="Is Welfare", store=True, tracking=True)