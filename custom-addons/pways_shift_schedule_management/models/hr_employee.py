from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.onchange('shift_id')
    def _onchange_shift(self):
        if self.shift_id and self.shift_id.calender_id:
            self.resource_calendar_id = self.shift_id.calender_id.id   

    shift_id = fields.Many2one("hr.shift", compute='_compute_shift_id', string="Shift", store=True)
    dayofweek_ids = fields.One2many('hr.day.of.week', 'employee_id', string="Week Days")
    dayofallocation_ids = fields.One2many('hr.day.of.allocation', 'employee_id', string="Working Days")
    shift_allocation_ids = fields.One2many('shift.allocation', 'employee_id', string="Allocation")

    @api.depends('dayofweek_ids', 'dayofallocation_ids')
    def _compute_shift_id(self):
        today = date.today()
        for emp in self:
            allocation_id = self.env['shift.allocation'].search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'in_progress'),
            ], limit=1) 
            emp.shift_id = allocation_id and allocation_id.shift_id.id or False
