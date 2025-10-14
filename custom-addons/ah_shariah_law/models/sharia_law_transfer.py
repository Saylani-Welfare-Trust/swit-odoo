from odoo import models, fields, api
from odoo.exceptions import UserError


class ShariahLawTransfer(models.TransientModel):
    _name = 'shariah.law.transfer'

    company_id = fields.Many2one('res.company', string='Company')
    currency_id = fields.Many2one('res.currency', 'Currency')

    shariah_law_id = fields.Many2one('shariah.law')
    restricted_account_id = fields.Many2one('account.analytic.account', 'Name')
    restricted_plan_id = fields.Many2one('account.analytic.plan')

    unrestricted_account_id = fields.Many2one('account.analytic.account', 'Name')
    unrestricted_plan_id = fields.Many2one('account.analytic.plan')

    transfer_to_partner_id = fields.Many2one('res.partner', 'Transfer to')
    transfer_from_partner_id = fields.Many2one('res.partner', 'Receive from')
    is_transfer_to = fields.Boolean()

    direction = fields.Selection([
        ('res_to_unres', 'Restricted to Unrestricted'),
        ('unres_to_res', 'Unrestricted to Restricted')],
        string='Direction', default='res_to_unres')

    amount = fields.Monetary('Amount', currency_field='currency_id')

    def action_transfer_to_confirm(self):

        debit_account = self.env.ref('ah_shariah_law.debit_account_transfer_to').account_id
        credit_account = self.env.ref('ah_shariah_law.credit_account_transfer_to').account_id

        if not debit_account:
            raise UserError('No Debit Account found')
        if not credit_account:
            raise UserError('No Credit Account found')

        dynamic_debit_field = f'x_plan{self.restricted_plan_id.id}_id'
        dynamic_debit_field_data = self.restricted_account_id.id

        # dynamic_debit_field = None
        # dynamic_debit_field_data = None
        #
        # dynamic_credit_field = None
        # dynamic_credit_field_data = None
        #
        # if self.direction == 'res_to_unres':
        #     dynamic_debit_field = f'x_plan{self.restricted_plan_id.id}_id'
        #     dynamic_debit_field_data = self.restricted_account_id.id
        #
        #     dynamic_credit_field = f'x_plan{self.unrestricted_plan_id.id}_id'
        #     dynamic_credit_field_data = self.unrestricted_account_id.id
        # else:
        #     dynamic_debit_field = f'x_plan{self.unrestricted_plan_id.id}_id'
        #     dynamic_debit_field_data = self.unrestricted_account_id.id
        #
        #     dynamic_credit_field = f'x_plan{self.restricted_plan_id.id}_id'
        #     dynamic_credit_field_data = self.restricted_account_id.id


        move_lines = [
            {
                'name': f'{self.restricted_account_id.name}',
                'account_id': debit_account.id,
                'debit': self.amount,
                'credit': 0.0,
                'analytic_line_ids': [
                    (0, 0, {'name': "Shariah Law", 'amount': -self.amount, 'unit_amount': 1, dynamic_debit_field: dynamic_debit_field_data}),
                ],
                'partner_id': self.transfer_to_partner_id.id,
                'currency_id': self.currency_id.id if self.currency_id else None,
            },
            {
                'name': f'{self.restricted_account_id.name}',
                'account_id': credit_account.id,
                'credit': self.amount,
                'debit': 0.0,
                'partner_id': self.transfer_to_partner_id.id,
                'currency_id': self.currency_id.id if self.currency_id else None,
            }
        ]

        move = self.env['account.move'].create({
            'ref': f'{self.restricted_account_id.name}',
            'partner_id': self.transfer_to_partner_id.id,
            # 'journal_id': journal.id,
            'line_ids': [(0, 0, line) for line in move_lines],
            'date': fields.Date.today(),
            'move_type': 'entry',
        })

        move.action_post()
        self.shariah_law_id.update_analytic_account()


    def action_transfer_back_confirm(self):

        debit_account = self.env.ref('ah_shariah_law.debit_account_transfer_back').account_id
        credit_account = self.env.ref('ah_shariah_law.credit_account_transfer_back').account_id

        if not debit_account:
            raise UserError('No Debit Account found')
        if not credit_account:
            raise UserError('No Credit Account found')


        dynamic_credit_field = f'x_plan{self.unrestricted_plan_id.id}_id'
        dynamic_credit_field_data = self.unrestricted_account_id.id


        move_lines = [
            {
                'name': f'{self.restricted_account_id.name}',
                'account_id': debit_account.id,
                'debit': self.amount,
                'credit': 0.0,
                'partner_id': self.transfer_from_partner_id.id,
                'currency_id': self.currency_id.id if self.currency_id else None,
            },
            {
                'name': f'{self.restricted_account_id.name}',
                'account_id': credit_account.id,
                'credit': self.amount,
                'debit': 0.0,
                'analytic_line_ids': [
                    (0, 0, {'name': "Shariah Law", 'amount': self.amount, 'unit_amount': 1, dynamic_credit_field: dynamic_credit_field_data}),
                ],
                'partner_id': self.transfer_from_partner_id.id,
                'currency_id': self.currency_id.id if self.currency_id else None,
            }
        ]

        move = self.env['account.move'].create({
            'ref': f'{self.restricted_account_id.name}',
            'partner_id': self.transfer_from_partner_id.id,
            # 'journal_id': journal.id,
            'line_ids': [(0, 0, line) for line in move_lines],
            'date': fields.Date.today(),
            'move_type': 'entry',
        })

        move.action_post()
        self.shariah_law_id.update_analytic_account()


