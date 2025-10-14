from odoo import models, fields, api
from odoo.exceptions import UserError


class ShariahLawAccountConf(models.Model):
    _name = 'shariah.law.account.conf'

    restricted_account_id = fields.Many2one('account.analytic.account', 'Restricted Account')
    unrestricted_account_id = fields.Many2one('account.analytic.account', 'Unrestricted Account')


class ShariahLawChartOfAccount(models.Model):
    _name = 'shariah.law.chart.of.account'

    name = fields.Char(string='Name')
    account_id = fields.Many2one('account.account', 'Chart of Account')
    account_type = fields.Selection([
        ('transfer_to', 'Transfer To'),
        ('transfer_back', 'Transfer Back')
    ])