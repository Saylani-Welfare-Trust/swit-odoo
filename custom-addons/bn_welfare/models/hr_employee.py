from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    area = fields.Many2many('area', string="Area", tracking=True)
    is_welfare_marfat = fields.Boolean(string="Is Welfare Disbursement Officer (Marfat)", default=False, tracking=True)


class HREmployeePublic(models.Model):
    _inherit = 'hr.employee.public'
    is_welfare_marfat = fields.Boolean(related='employee_id.is_welfare_marfat', compute_sudo=True, string="Is Welfare Disbursement Officer (Marfat)", store=True)