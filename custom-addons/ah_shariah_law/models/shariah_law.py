from odoo import models, fields, api
from odoo.exceptions import UserError

class ShariahLaw(models.Model):
    _name = 'shariah.law'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Currency",
    )

    restricted_account_id = fields.Many2one('account.analytic.account', 'Name')
    restricted_plan_id = fields.Many2one('account.analytic.plan')
    restricted_amount = fields.Monetary('Restricted Amount', currency_field='currency_id')

    unrestricted_account_id = fields.Many2one('account.analytic.account', 'Name')
    unrestricted_plan_id = fields.Many2one('account.analytic.plan')
    unrestricted_amount = fields.Monetary('Unrestricted Amount', currency_field='currency_id')


    def update_analytic_account(self):
        shariah_law_accounts = self.env['shariah.law.account.conf'].search([])

        all_records = self.env['shariah.law'].search([])
        all_records.sudo().unlink()

        if shariah_law_accounts:
            for account in shariah_law_accounts:
                self.env['shariah.law'].sudo().create({
                    'restricted_account_id': account.restricted_account_id.id,
                    'restricted_plan_id': account.restricted_account_id.plan_id.id,
                    'restricted_amount': account.restricted_account_id.balance,

                    'unrestricted_account_id': account.unrestricted_account_id.id,
                    'unrestricted_plan_id': account.unrestricted_account_id.plan_id.id,
                    'unrestricted_amount': account.unrestricted_account_id.balance,
                })

    def action_transfer_amount(self):
        for rec in self:
            action = self.env.ref('ah_shariah_law.action_shariah_law_wizard').read()[0]
            form_view_id = self.env.ref('ah_shariah_law.ah_view_sharia_law_wizard_form').id
            action['views'] = [
                [form_view_id, 'form']
            ]
            action['context'] = {
                'default_company_id': self.company_id.id,
                'default_currency_id': self.currency_id.id,
                'default_shariah_law_id': self.id,
                'default_is_transfer_to': True,
                'default_restricted_account_id': self.restricted_account_id.id,
                'default_restricted_plan_id': self.restricted_plan_id.id,
                'default_unrestricted_account_id': self.unrestricted_account_id.id,
                'default_unrestricted_plan_id': self.unrestricted_plan_id.id
            }
            return action


    def action_receive_amount(self):
        for rec in self:
            action = self.env.ref('ah_shariah_law.action_shariah_law_wizard').read()[0]
            form_view_id = self.env.ref('ah_shariah_law.ah_view_sharia_law_wizard_form').id
            action['views'] = [
                [form_view_id, 'form']
            ]
            action['context'] = {
                'default_company_id': self.company_id.id,
                'default_currency_id': self.currency_id.id,
                'default_shariah_law_id': self.id,
                'default_is_transfer_to': False,
                'default_restricted_account_id': self.restricted_account_id.id,
                'default_restricted_plan_id': self.restricted_plan_id.id,
                'default_unrestricted_account_id': self.unrestricted_account_id.id,
                'default_unrestricted_plan_id': self.unrestricted_plan_id.id
            }
            return action





