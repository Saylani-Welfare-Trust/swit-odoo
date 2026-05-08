from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    area = fields.Many2many('area', string="Area", tracking=True)
    is_welfare_marfat = fields.Boolean(string="Is Welfare Disbursement Officer (Marfat)", default=False, tracking=True)