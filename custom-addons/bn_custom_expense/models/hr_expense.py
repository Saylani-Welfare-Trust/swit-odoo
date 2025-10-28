from odoo import models, api, fields
from odoo.exceptions import ValidationError


class HRExpense(models.Model):
    _inherit = 'hr.expense'


    is_record_created = fields.Boolean('Is Record Created', default=False)


    @api.onchange('date')
    def _onchange_date(self):
        if self.date > fields.Date.today():
            raise ValidationError('Expense can not be recorded on Future Dates.')
    
    @api.onchange('payment_mode')
    def _onchange_payment_mode(self):
        if self.payment_mode == 'company_account':
            raise ValidationError('Expense payment mode can be set as ( Company ).')
        
    @api.model
    def create(self, vals):
        vals['is_record_created'] = True

        return super(HRExpense, self).create(vals)