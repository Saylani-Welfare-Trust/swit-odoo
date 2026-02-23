from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    
    is_receive_by_weight = fields.Boolean(related='product_tmpl_id.is_receive_by_weight', string="Is Receive By Weight", store=True, tracking=True)