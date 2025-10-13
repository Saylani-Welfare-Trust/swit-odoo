from odoo import models, fields, api
from odoo.exceptions import UserError
import base64
class PosSession(models.Model):
    _inherit = 'pos.session'


    pos_attachment_id = fields.Binary(string='POS Attachment')
    pos_attachment_name = fields.Char()

    @api.model
    def session_journal_entry(self, data):
        session = self.browse(data['session_id'])
        # print(data, 'data')
        if data['file_data']:
            decoded_data = base64.b64decode(data['file_data'])
            attachment = self.env['ir.attachment'].create({
                'name': data['file_name'],
                'type': 'binary',
                'datas': base64.b64encode(decoded_data),  # Encode it back to base64 for storage
                'res_model': 'pos.session',
                'res_id': session.id,  # Link the attachment to the current POS session
            })
            session.write({
                'pos_attachment_id': attachment.datas,
                'pos_attachment_name': attachment.name
            })
            attachment.unlink()


        # cash_payment_method = self.env['pos.payment.method'].search([
        #     ('is_cash', '=', True)
        # ], limit=1)
        # session_cash_records = self.env['pos.payment'].search([
        #     ('session_id', '=', data['session_id']),
        #     ('payment_method_id', '=', cash_payment_method.id)
        # ])
        #
        # cash_total_amount = sum(session_cash_records.mapped('amount'))
        #
        # cash_credit_account = cash_payment_method.cash_credit_account
        # cash_debit_account = cash_payment_method.cash_debit_account
        #
        # if not cash_credit_account:
        #     raise UserError('No Credit Account found')
        # if not cash_debit_account:
        #     raise UserError('No Debit Account found')
        #
        # move_lines = [
        #     {
        #         'name': f'{session.name}',
        #         'account_id': cash_credit_account.id,
        #         'credit': cash_total_amount,
        #         'debit': 0.0,
        #         'currency_id': session.currency_id.id if session.currency_id else None,
        #     },
        #     {
        #         'name': f'{session.name}',
        #         'account_id': cash_debit_account.id,
        #         'debit': cash_total_amount,
        #         'credit': 0.0,
        #         'currency_id': session.currency_id.id if session.currency_id else None,
        #     }
        # ]
        # move = self.env['account.move'].create({
        #     'ref': f'{session.name}',
        #     # 'journal_id': journal.id,
        #     'line_ids': [(0, 0, line) for line in move_lines],
        #     'date': fields.Date.today(),
        #     'move_type': 'entry',
        # })
        # move.action_post()
        #
        #
        # bank_payment_method = self.env['pos.payment.method'].search([
        #     ('is_bank', '=', True)
        # ], limit=1)
        # session_bank_records = self.env['pos.payment'].search([
        #     ('session_id', '=', data['session_id']),
        #     ('payment_method_id', '=', bank_payment_method.id)
        # ])
        #
        # bank_total_amount = sum(session_bank_records.mapped('amount'))
        #
        # bank_credit_account = bank_payment_method.bank_credit_account
        # bank_debit_account = bank_payment_method.bank_debit_account
        #
        # if not bank_credit_account:
        #     raise UserError('No Credit Account found')
        # if not bank_debit_account:
        #     raise UserError('No Debit Account found')
        #
        # move_lines = [
        #     {
        #         'name': f'{session.name}',
        #         'account_id': bank_credit_account.id,
        #         'credit': bank_total_amount,
        #         'debit': 0.0,
        #         'currency_id': session.currency_id.id if session.currency_id else None,
        #     },
        #     {
        #         'name': f'{session.name}',
        #         'account_id': bank_debit_account.id,
        #         'debit': bank_total_amount,
        #         'credit': 0.0,
        #         'currency_id': session.currency_id.id if session.currency_id else None,
        #     }
        # ]
        # move = self.env['account.move'].create({
        #     'ref': f'{session.name}',
        #     # 'journal_id': journal.id,
        #     'line_ids': [(0, 0, line) for line in move_lines],
        #     'date': fields.Date.today(),
        #     'move_type': 'entry',
        # })
        # move.action_post()

