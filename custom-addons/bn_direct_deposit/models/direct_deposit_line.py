from odoo import models, fields


class DirectDepositLine(models.Model):
    _name = 'direct.deposit.line'
    _description = "Direct Deposit Line"


    direct_deposit_id = fields.Many2one('direct.deposit', string="Direct Deposit")
    product_id = fields.Many2one('product.product', string="Product")
    currency_id = fields.Many2one('res.currency', related='direct_deposit_id.currency_id')
    
    quantity = fields.Integer('Quantity', default=1)

    amount = fields.Monetary('Amount', currency_field='currency_id')