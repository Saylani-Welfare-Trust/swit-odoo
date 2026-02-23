from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    
    is_receive_by_weight = fields.Boolean('Is Receive By Weight', tracking=True)