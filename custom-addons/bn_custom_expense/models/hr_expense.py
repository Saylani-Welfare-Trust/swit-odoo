from odoo import models, api, fields
from odoo.exceptions import ValidationError

from datetime import timedelta


class HRExpense(models.Model):
    _inherit = 'hr.expense'


    @api.onchange('date')
    def _onchange_date(self):
        if self.date:
            today = fields.Date.today()
            three_months_ago = today - timedelta(days=90)  # roughly 3 months

            if self.date > today:
                raise ValidationError('Expense cannot be recorded on future dates.')

            if self.date < three_months_ago:
                raise ValidationError('Expense date cannot be older than 3 months.')
    
    @api.onchange('payment_mode')
    def _onchange_payment_mode(self):
        if self.payment_mode == 'company_account':
            raise ValidationError('Expense payment mode can be set as ( Company ).')