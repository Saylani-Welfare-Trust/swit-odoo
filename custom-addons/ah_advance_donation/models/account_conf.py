from odoo import models,fields,api

class AdvDonAccountConf(models.Model):
    _name = 'ah.adv.don.account.conf'
    _order = 'create_date asc'

    name = fields.Char(string='Name')
    account_id = fields.Many2one('account.account', 'Chart of Account')
    account_type = fields.Selection([
        ('payment_conf_cash', 'Payment Configuration (Cash)'),
        ('deposit_conf_cheque', 'Deposit Configuration (Cheque)'),
        ('payment_conf_cheque', 'Payment Configuration (Cheque)')
    ])