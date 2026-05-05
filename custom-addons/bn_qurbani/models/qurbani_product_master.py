from odoo import models, fields


class QurbaniProductMaster(models.Model):
    _name = 'qurbani.product.master'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Qurbani Product Master"


    inventory_product_id = fields.Many2one('product.product', string='Inventory Product', tracking=True)

    inventory_product_name = fields.Char(related='inventory_product_id.name', string="Inentory Product Name")
    
    pos_product_ids = fields.Many2many('product.product', string="POS Products", tracking=True)