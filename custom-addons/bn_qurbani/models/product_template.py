from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'


    is_qurbani_inventory = fields.Boolean('Is Qurbani Inventory', default=False)
    is_pos_qurbani_inventory = fields.Boolean('Is POS Qurbani Inventory', default=False)