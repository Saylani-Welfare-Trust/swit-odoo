from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    
    is_livestock = fields.Boolean('Is Livestock', tracking=True)