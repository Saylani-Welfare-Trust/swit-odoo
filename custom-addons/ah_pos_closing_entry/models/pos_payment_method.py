from odoo import models, fields, api

class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    is_cash = fields.Boolean(string='Is Cash?')
    is_bank = fields.Boolean(string='Is Bank?')

    bank_credit_account = fields.Many2one('account.account', 'Credit Account')
    bank_debit_account = fields.Many2one('account.account', 'Debit Account')

    cash_credit_account = fields.Many2one('account.account', 'Credit Account')
    cash_debit_account = fields.Many2one('account.account', 'Debit Account')