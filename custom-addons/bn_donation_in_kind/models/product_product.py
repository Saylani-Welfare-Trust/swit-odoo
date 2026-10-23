from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'


    is_donation_in_kind = fields.Boolean(related='product_tmpl_id.is_donation_in_kind', store=True, tracking=True)