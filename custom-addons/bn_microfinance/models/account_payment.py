from odoo import models
from odoo.exceptions import UserError 

class AccountRegisterPayments(models.TransientModel):
    _inherit = 'account.payment.register'

    def _prepare_payment_vals(self, invoices):
        res = super()._prepare_payment_vals(invoices)
        # Link payment to microfinance if bill is linked
        if invoices:
            bill = invoices[0]
            if bill.ref:
                microfinance = self.env['microfinance'].search([
                    ('name', '=', bill.ref)
                ], limit=1)
                if microfinance:
                    res['ref'] = bill.ref
        return res
    
    def action_create_payments(self):
        res = super().action_create_payments()


        microfinance = self.env['microfinance'].search([
            ('name', '=', self.communication)
        ], limit=1)

        if microfinance and microfinance.asset_type == 'cash':
            if microfinance.state == 'treasury':
                microfinance._complete_application()

        return res



