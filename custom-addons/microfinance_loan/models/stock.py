from odoo import models, fields, api
from datetime import date

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_microfinance_loan = fields.Boolean()
    microfinance_loan_id = fields.Many2one('mfd.loan.request', 'Microfinance Loan')

    def button_validate(self):

        res = super(StockPicking, self).button_validate()

        if self.is_microfinance_loan and self.microfinance_loan_id:
            self.microfinance_loan_id.write({'disbursement_date': date.today()})
            self.microfinance_loan_id.action_done()

        return res