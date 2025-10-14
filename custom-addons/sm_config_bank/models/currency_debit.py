from odoo import fields, models


class CurrencyDebit(models.Model):
    _name = 'currency.debit'
    _description = "Config Bank Line"

    config_bank_id = fields.Many2one('config.bank', string="Config Bank ID")

    currency_id = fields.Many2one('res.currency', string="Currency ID")
    account_id = fields.Many2one('account.account', string="Debit Account ID")