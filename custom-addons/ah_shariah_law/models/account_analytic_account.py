from odoo import models, fields, api

class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    is_restricted = fields.Boolean()
    unrestricted_account_id = fields.Many2one('account.analytic.account', 'Unrestricted Account')