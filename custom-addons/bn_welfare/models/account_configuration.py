from odoo import fields, models


class MfdAccountConfiguration(models.Model):
    _name = 'welfare.account.configuration'
    _order = 'create_date asc'

    name = fields.Char(string='Name')
    account_id = fields.Many2one('account.account', 'Chart of Account')