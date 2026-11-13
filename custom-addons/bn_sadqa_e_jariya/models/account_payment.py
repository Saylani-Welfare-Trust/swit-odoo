from odoo import models, api


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _sadqa_jariya_lines(self):
        """Sadqa e Jariya lines of the bills being paid"""
        bills = self.line_ids.move_id
        return bills.sadqa_jariya_line_id, bills.sadqa_jariya_recurring_line_id

    @api.onchange('source_amount', 'source_amount_currency', 'source_currency_id', 'company_id', 'currency_id', 'payment_date', 'line_ids')
    def _onchange_sadqa_jariya_bank_reference(self):
        """Pay to the account the institution gave in its form"""
        lines, recurring_lines = self._sadqa_jariya_lines()
        application = (recurring_lines or lines)[:1].application_id
        if application:
            bank_ref = application.account_number or application.donee_id.bank_wallet_account
            if bank_ref:
                self.bank_reference = bank_ref

    def action_create_payments(self):
        res = super().action_create_payments()
        # Bank lines are disbursed once their bill is paid
        for lines in self._sadqa_jariya_lines():
            lines.filtered(lambda l: l.state == 'delivered').action_disbursed()
        return res
