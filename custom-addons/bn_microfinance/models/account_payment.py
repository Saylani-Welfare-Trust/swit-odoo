from odoo import models

class AccountRegisterPayments(models.TransientModel):
    _inherit = 'account.payment.register'

    def _prepare_payment_vals(self, invoices):
        res = super()._prepare_payment_vals(invoices)
        # Link payment to microfinance if bill is linked
        if invoices:
            bill = invoices[0]
            if bill.ref:
                microfinance = self.env['microfinance'].sudo().search([
                    ('name', '=', bill.ref)
                ], limit=1)
                if microfinance:
                    res['ref'] = bill.ref
        return res
    
    def action_create_payments(self):
        """A cash loan in Treasury is completed once its disbursement bill is
        paid: found through the bills this payment pays (not through the memo,
        which anyone can type), and only when they are fully paid."""
        bills = self.line_ids.move_id
        res = super().action_create_payments()
        loans = self.env['microfinance'].sudo().search([
            ('bill_ids', 'in', bills.ids), ('asset_type', '=', 'cash'), ('state', '=', 'treasury')])
        for loan in loans:
            posted = loan.bill_ids.filtered(lambda bill: bill.state == 'posted')
            if posted and all(bill.payment_state in ('paid', 'in_payment') for bill in posted):
                loan._complete_application()
        return res
