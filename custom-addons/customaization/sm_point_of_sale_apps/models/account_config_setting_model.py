from odoo import api, fields, models, _


class AccountConfigSettingsModel(models.Model):
    _name = 'account.config.settings'
    _description = 'Account Config Settings'
    _rec_name = 'model_id'

    model_id = fields.Many2one(comodel_name='ir.model', string='Model', required=True, ondelete='cascade')
    journal_id = fields.Many2one(comodel_name='account.journal', string='Journal', required=True)
    debit_account_id = fields.Many2one(comodel_name='account.account', string='Account (Dr)', required=True)
    credit_account_id = fields.Many2one(comodel_name='account.account', string='Account (Cr)', required=True)

