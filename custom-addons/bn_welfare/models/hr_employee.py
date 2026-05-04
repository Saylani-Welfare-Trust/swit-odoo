from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    area = fields.Many2many('area', string="Area", tracking=True)