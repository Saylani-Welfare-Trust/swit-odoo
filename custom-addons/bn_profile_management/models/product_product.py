from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'


    is_course = fields.Boolean(related='product_tmpl_id.is_course', string="Is Course", store=True, tracking=True)