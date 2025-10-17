from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    
    is_donation_box = fields.Boolean('Is Donation Box', tracking=True)