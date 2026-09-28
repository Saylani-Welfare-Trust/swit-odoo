from odoo import models, fields


class ProductMasterLine(models.Model):
    _name = 'product.master.line'
    _description = "Product Master Line"


    product_master_id = fields.Many2one('product.master', string="Product Master")
    product_id = fields.Many2one('product.product', string="Product")

    quantity = fields.Integer('Quantity')