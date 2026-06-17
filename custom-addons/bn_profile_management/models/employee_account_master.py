from odoo import models, fields


class EmployeeAccountMaster(models.Model):
    _name = 'employee.account.master'
    _description = 'Employee Account Master'


    advance_account_code = fields.Char('Advance Account Code')
    petty_cash_account_code = fields.Char('Petty Cash Account Code')