from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta

class HrShiftRequest(models.Model):
    _name = "hr.shift.request"
    _description = "Shift Change Request"
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Name", required=True, index=True, readonly=True, copy=False, default='New')
    employee_id = fields.Many2one('hr.employee', string="Employee")
    allocation_id = fields.Many2one('shift.allocation', string="Allocation")
    changed_day = fields.Selection([('weekoff', 'Weekoff'),('working_days', 'Working Days')], default='working_days', string="Type")
    week_off_ids_vr = fields.Many2many('hr.day.of.week', relation="employee_hr_week_of",  string="Week Off", compute="_compute_week_off_ids", store=True)
    week_off_ids = fields.Many2many('hr.day.of.week', string="Week Off")
    working_day_ids_vr = fields.Many2many('hr.day.of.allocation', relation="employee_hr_day_of_allocation", string="Working day")
    working_day_ids = fields.Many2many('hr.day.of.allocation', string="Working day")
    shift_id = fields.Many2one('hr.shift', string="Shift")
    description = fields.Text(string="Description")
    state = fields.Selection([('draft', 'Draft'),('in_progress', 'In Progress'),('approved', 'Approved'),('cancel','Cancel')], default='draft')
    company_id = fields.Many2one('res.company', 'Company',  default=lambda self: self.env.user.company_id)
    user_id = fields.Many2one('res.users', string="Responsible", default=lambda self: self.env.user)

    @api.depends('allocation_id')
    def _compute_week_off_ids(self):
        for shift in self:
            shift.week_off_ids_vr = shift.allocation_id.mapped('dayofweek_ids').ids
            shift.working_day_ids_vr = shift.allocation_id.mapped('dayofallocation_ids').ids

    @api.onchange('changed_day')
    def onchange_branch_id(self):
        if self.changed_day == 'weekoff':
            self.working_day_ids = [(5,0,0)]
        if self.changed_day == "working_days":
            self.week_off_ids = [(5,0,0)]

    def shift_request(self):
        self.write({'state': 'in_progress'})

    def shift_approval(self):
        for weekoff in self.week_off_ids:
            weekoff.write({'shift_id': self.shift_id.id})
        for working_day in self.working_day_ids:
            working_day.write({'shift_id': self.shift_id.id})
        email = self.env.user.email
        template_id = self.env.ref('pways_shift_schedule_management.shift_change_request_send_employee')
        email_to = self.employee_id.work_email
        template_id.with_context(from_email=email, email_to=email_to).sudo().send_mail(self.id, force_send=True)
        self.write({'state': 'approved'})

    def shift_cancel(self):
        self.write({'state': 'cancel'})

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = super(HrShiftRequest, self).create(vals_list)
        for vals in vals_list:
            vals.name = self.env['ir.sequence'].next_by_code('hr.shift.request') or '/'
        return vals_list
