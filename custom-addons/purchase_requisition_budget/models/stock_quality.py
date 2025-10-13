from odoo import models, fields


class StockQualityCheck(models.Model):
    _name = 'stock.quality.check'

    product_id = fields.Many2one('product.product', string="Product", required=True)
    quality_check = fields.Selection([
        ('default', 'Default'),
        ('pass', 'Pass'),
        ('fail', 'Fail'),
    ], string="Quality Check", default='default')
    stock_picking_id = fields.Many2one('stock.picking', string="Stock Picking")
