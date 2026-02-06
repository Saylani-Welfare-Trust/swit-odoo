from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'


    is_advance_donation = fields.Boolean(related='product_tmpl_id.is_advance_donation', string="Is Advance Donation")