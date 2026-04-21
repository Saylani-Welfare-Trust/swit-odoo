from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'


    is_qurbani_inventory = fields.Boolean(related='product_tmpl_id.is_qurbani_inventory', string="Is Qurbani Inventory", store=True, tracking=True)