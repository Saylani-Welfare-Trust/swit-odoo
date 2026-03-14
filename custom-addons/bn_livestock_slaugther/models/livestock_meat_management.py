from odoo import models, fields


class LivestockMeatManagement(models.Model):
    _name = 'livestock.meat.management'
    _description = "Livestock Meat Management"


    meat_management_id = fields.Many2one('meat.management', string="Meat Management")
    product_id = fields.Many2one('product.product', string="Product")
    location_id = fields.Many2one('stock.location', string="Location")

    date = fields.Date('Date')

    quantity = fields.Float('Quantity')