from odoo import models, fields


class HREmployeePublic(models.Model):
    _inherit = 'hr.employee.public'


    analytic_account_id = fields.Many2one(related='employee_id.analytic_account_id', compute_sudo=True, string="Analytic Account", store=True)
    
    cnic_no = fields.Char(related='employee_id.cnic_no', compute_sudo=True, string="CNIC No.", store=True)