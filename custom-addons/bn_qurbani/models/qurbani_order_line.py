from odoo import models, fields


class QurbaniOrderLine(models.Model):
    _name = 'qurbani.order.line'
    _description = "Qurbani Order Line"


    qurbani_order_id = fields.Many2one('qurbani.order', string="Qurbani Order")
    product_id = fields.Many2one('product.product', string="Product")
    currency_id = fields.Many2one('res.currency', related='qurbani_order_id.currency_id')

    quantity = fields.Integer('Quantity', default=1)

    amount = fields.Monetary('Amount', currency_field='currency_id')

    remarks = fields.Char('Remarks')