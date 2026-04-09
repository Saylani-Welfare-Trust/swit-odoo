from odoo import models, fields


class QurbaniOrder(models.Model):
    _name = 'qurbani.order'
    _description = 'Qurbani POS Orders'

    pos_order_id = fields.Many2one('pos.order', string="Order", required=True)
    receipt_number = fields.Char(string="Receipt Number", required=True)
    product_ids = fields.Many2many('product.product', string="Products")