from odoo import models, fields


class HREmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    # The branch is shown to everybody; the CNIC is not (HR only, on hr.employee).
    analytic_account_id = fields.Many2one(related='employee_id.analytic_account_id', compute_sudo=True, string="Analytic Account", store=True)
