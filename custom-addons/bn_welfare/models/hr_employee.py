from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    area = fields.Many2many('area', string="Area", tracking=True)
    is_welfare_marfat = fields.Boolean(string="Is Welfare Disbursement Officer (Marfat)", default=False, tracking=True)


class HREmployeePublic(models.Model):
    _inherit = 'hr.employee.public'
    # area = fields.Many2many(related='employee_id.area', compute_sudo=True, string="Area", store=True)
    is_welfare_marfat = fields.Boolean(related='employee_id.is_welfare_marfat', compute_sudo=True, string="Is Welfare Disbursement Officer (Marfat)", store=True)