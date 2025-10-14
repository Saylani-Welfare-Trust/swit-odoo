from odoo import models, api, fields, _



class ProductProduct(models.Model):
    _inherit = 'product.product'

    for_credit_clear = fields.Many2one('account.account',string='Credit For Clear Cheque')

    for_debit_clear = fields.Many2one('account.account',string='Debit for Clear Cheque')


    for_credit_bounce = fields.Many2one('account.account',string='Credit For Bounce Cheque')

    for_debit_bounce = fields.Many2one('account.account',string='Debit for Bounce Cheque')


    online_payment_method_id = fields.Many2one('pos.payment.method',string='Payment method')
    product_entry_line = fields.One2many('product.product.entry','product_id',string='Entry Line')


class ProductEnterLine(models.Model):
    _name = 'product.product.entry'

    product_id = fields.Many2one('product.product')
    for_credit = fields.Many2one('account.account',string='For Credit')

    for_debit = fields.Many2one('account.account',string='For Debit')
    online_payment_method_id = fields.Many2one('pos.payment.method',string='Payment method')

