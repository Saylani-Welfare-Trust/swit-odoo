from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    
    is_donation_box = fields.Boolean(related='product_tmpl_id.is_donation_box', string="Is Donation Box", store=True, tracking=True)