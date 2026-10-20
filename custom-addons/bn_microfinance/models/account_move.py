from odoo import models

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        res = super().action_post()
        # After bill is confirmed (posted), check if it's linked to a microfinance record
        for bill in self:
            if bill.ref:
                microfinance = self.env['microfinance'].search([
                    ('name', '=', bill.ref)
                ], limit=1)
                if microfinance and microfinance.asset_type == 'cash':
                        if microfinance.state in ['treasury']:
                            microfinance._complete_application()
        return res
