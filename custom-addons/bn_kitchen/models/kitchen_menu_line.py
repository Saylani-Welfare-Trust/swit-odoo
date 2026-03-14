from odoo import models, fields


class KitchenMenuLine(models.Model):
    _name = 'kitchen.menu.line'
    _description = "Kitchen Menu Line"


    kitchen_menu_id = fields.Many2one('kitchen.menu', string="Kitchen Menu")

    product_id = fields.Many2one('product.product', string="Product")

    quantity = fields.Float('Quantity', default=1)