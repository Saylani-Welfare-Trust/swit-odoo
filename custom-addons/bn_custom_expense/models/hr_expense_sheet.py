from odoo import models
from odoo.exceptions import ValidationError
from odoo.tools.misc import clean_context


class HRExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'


    def _do_create_moves(self):
        self = self.with_context(clean_context(self.env.context))  # remove default_*
        skip_context = {
            'skip_invoice_sync': True,
            'skip_invoice_line_sync': True,
            'skip_account_move_synchronization': True,
        }
        own_account_sheets = self.filtered(lambda sheet: sheet.payment_mode == 'own_account')
        company_account_sheets = self - own_account_sheets

        moves = self.env['account.move'].create([sheet._prepare_bills_vals() for sheet in own_account_sheets])
        # Set the main attachment on the moves directly to avoid recomputing the
        # `register_as_main_attachment` on the moves which triggers the OCR again
        for move in moves:
            move.message_main_attachment_id = move.attachment_ids[0] if move.attachment_ids else None
        payments = self.env['account.payment'].with_context(**skip_context).create([
            expense._prepare_payments_vals() for expense in company_account_sheets.expense_line_ids
        ])
        moves |= payments.move_id
        # moves.action_post()
        self.activity_update()

        return moves
    
    def action_reset_approval_expense_sheets(self):
        if self.state == 'approve':
            raise ValidationError('Cannot set an approve expense to draft.')
        
        return super(HRExpenseSheet, self).action_reset_approval_expense_sheets()
    
    def unlink(self):
        raise UserError(_('You cannot delete an expense sheet.'))
        # if self.state == 'approve':
        #     raise ValidationError('No one have right to delete an approved expense sheet.')
        
        # return super(HRExpenseSheet, self).unlink()
