from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    
    is_livestock = fields.Boolean(related='product_tmpl_id.is_livestock', string="Is Livestock", store=True, tracking=True)