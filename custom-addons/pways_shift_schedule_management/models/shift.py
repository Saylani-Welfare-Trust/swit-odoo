from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta

class ShiftType(models.Model):
    _name = "shift.type"
    _description = "shift.type"

    name = fields.Char(required=True)
    work_hours = fields.Float(string="Work Hours")

class ShiftAllocation(models.Model):
    _name = "shift.allocation"
    _description = "shift allocation"
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Name', required=True, index=True, readonly=True, copy=False, default='New')
    date_from = fields.Date()
    date_to = fields.Date()
    shift_id = fields.Many2one("hr.shift")
    employee_id = fields.Many2one("hr.employee")
    state = fields.Selection([('draft', 'Draft'),('in_progress', 'Done'),('cancel','Cancel')], default='draft')
    description = fields.Text()
    shift_type_id = fields.Many2one('shift.type')
    dayofweek_ids = fields.One2many('hr.day.of.week', 'shift_allocation_id', string="Lines")
    dayofallocation_ids = fields.One2many('hr.day.of.allocation', 'shift_allocation_id', string='Lines')
    company_id = fields.Many2one('res.company', 'Company',  default=lambda self: self.env.user.company_id)

    @api.onchange('shift_id')
    def _onchange_shift(self):
        if self.shift_id:
            self.date_from = self.shift_id.date_from
            self.date_to = self.shift_id.date_to

    @api.constrains('employee_id','date_from','date_to')
    def check_validation(self):
        # Overlapping Not working
        for rec in self:
            match_shift = self.env['shift.allocation'].search([
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('date_from', '<=', rec.date_from), ('date_to', '>=', rec.date_to)
            ])
            if match_shift:
                raise ValidationError(_('Shift allocation are already defined for these dates'))

    @api.model
    def create(self, vals):
        res = super(ShiftAllocation, self).create(vals)
        res.name = self.env['ir.sequence'].next_by_code('hr.shift.allocation') or '/'
        # email = self.env.user.email
        # template_id = self.env.ref('pways_shift_schedule_management.email_template_shift_send')
        # email_to = res.employee_id.work_email
        # template_id.with_context(from_email=email, email_to=email_to).sudo().send_mail(res.id, force_send=True)
        return res

    def name_get(self):
        res = []
        for rec in self:
            name = rec.name
            if rec.employee_id and rec.shift_id:
                name = "%s - %s" % (rec.employee_id.name, rec.shift_id.name)
            res += [(rec.id, name)]
        return res

    def button_in_progress(self):
        self.write({'state' :'in_progress'})

    def button_closed(self):
        self.write({'state': 'cancel'})

class HrShift(models.Model):
    _name = 'hr.shift'
    _description = "hr.shift"

    name = fields.Char(required=True)
    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")
    calender_id = fields.Many2one('resource.calendar',string="Working Hours")
    shift_type_id = fields.Many2one('shift.type')
    time_from = fields.Float(string="Time From")
    time_too = fields.Float(string="Time To")
    overtime_threshold = fields.Float(string="Overtime Threshold")
    late_threshold = fields.Float(string="Late Threshold")
    notes = fields.Text(string="Description")
    count_weekoff = fields.Integer(string="Weekoff", compute="_compute_count_weekoff")
    count_allocation_day = fields.Integer(string="Allocation Day", compute="_compute_count_allocation_day")
    count_allocation = fields.Integer(string="Allocation", compute="_compute_count_allocation")
    responsible_id = fields.Many2one('res.users', string="Responsible", default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', 'Company',  default=lambda self: self.env.user.company_id)
    priority = fields.Selection([('0', 'Normal'), ('1', 'Urgent')], default='0', string="Priority")

    def _compute_count_weekoff(self):
        for shift in self:
            week_off_ids = self.env['hr.day.of.week'].search([('shift_id', '=', shift.id)])
            shift.count_weekoff = len(week_off_ids.ids)

    def _compute_count_allocation_day(self):
        for shift in self:
            week_day_ids = self.env['hr.day.of.allocation'].search([('shift_id', '=', shift.id)])
            shift.count_allocation_day = len(week_day_ids.ids)

    def _compute_count_allocation(self):
        for shift in self:
            allocation_ids = self.env['shift.allocation'].search([('shift_id', '=', shift.id)])
            shift.count_allocation = len(allocation_ids.ids)

    @api.constrains('shift_type_id','date_from','date_to')
    def check_validation(self):
        for rec in self:
            shift = self.env['hr.shift'].search([
                ('id', '!=', rec.id),
                ('shift_type_id', '=', rec.shift_type_id.id),
                ('date_from', '<=', rec.date_from), ('date_to', '>=', rec.date_to)
            ])
            if shift: 
                raise ValidationError(_('Shift allocation are already defined for these dates'))

    def action_open_weekoff(self):
        week_off_ids = self.env['hr.day.of.week'].search([('shift_id', '=', self.id)])
        return {
            'name': _('Weekoff'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'hr.day.of.week',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', week_off_ids.ids)],
        }

    def action_open_allocation_day(self):
        week_day_ids = self.env['hr.day.of.allocation'].search([('shift_id', '=', self.id)])
        return {
            'name': _('Weekdays'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'hr.day.of.allocation',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', week_day_ids.ids)],
        }

    def action_open_allocation(self):
        allocation_ids = self.env['shift.allocation'].search([('shift_id', '=', self.id)])
        return {
            'name': _('Allocation'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'shift.allocation',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', allocation_ids.ids)],
        }

class HrShiftDayofWeek(models.Model):
    _name = 'hr.day.of.week'
    _description = "Hr day of weeks"

    name = fields.Char(string="Name")
    employee_id = fields.Many2one('hr.employee', string="Employee")
    date = fields.Date(string="Date of Week")
    shift_allocation_id = fields.Many2one('shift.allocation', string="Shift Allocation")
    week_id = fields.Many2one('week.week', string="Day of Week")
    duration_type_id = fields.Many2one('hr.duration.type', string="Type")
    department_id = fields.Many2one(related='employee_id.department_id', string="Department", store=True)
    shift_id = fields.Many2one('hr.shift', string="Shift")
    job_id = fields.Many2one(related="employee_id.job_id", string="Job Position", store=True)
    week_selection_id = fields.Many2one('week.selection', string="Week Selection")
    create_date = fields.Date(string="Create Date", default=lambda self: date.today())
    user_id = fields.Many2one('res.users', string="Responsible", default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', 'Company',  default=lambda self: self.env.user.company_id)

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = super(HrShiftDayofWeek, self).create(vals_list)
        for vals in vals_list:
            vals.name = "%s/%s" %(vals.employee_id.name, vals.date)
        return vals_list

    @api.constrains('date')
    def _check_duplicate_date(self):
        for shift in self:
            week_ids = self.env['hr.day.of.week'].search_count([('date', '=', shift.date),('employee_id', '=', shift.employee_id.id), ('shift_id', '=', shift.shift_id.id), ('week_id', '=', shift.week_id.id), ('week_selection_id', '=', shift.week_selection_id.id)])
            if week_ids > 1:
                raise ValidationError(("Employee %s has duplicate week end entry on date %s for shift %s") % (shift.employee_id.name, shift.date, shift.shift_id.name))

class HrShiftDayofAllocation(models.Model):
    _name = 'hr.day.of.allocation'
    _description = "Hr day of Allocation"

    employee_id = fields.Many2one('hr.employee', string="Employee")
    name = fields.Char(string="Name")
    date = fields.Date(string="Date of week")
    shift_allocation_id = fields.Many2one('shift.allocation', string="Shift Allocation")
    duration_type_id = fields.Many2one('hr.duration.type', string="Type")
    shift_id = fields.Many2one('hr.shift', string="Shift")
    department_id = fields.Many2one(related='employee_id.department_id', string="Department", store=True)
    job_id = fields.Many2one(related="employee_id.job_id", string="Job Position", store=True)
    create_date = fields.Date(string="Create Date", default=lambda self: date.today())
    user_id = fields.Many2one('res.users', string="Responsible", default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', 'Company',  default=lambda self: self.env.user.company_id)

    @api.constrains('date')
    def _check_duplicate_date(self):
        for shift in self:
            allocation_ids = self.env['hr.day.of.allocation'].search_count([('date', '=', shift.date),('employee_id', '=', shift.employee_id.id), ('shift_id', '=', shift.shift_id.id)])
            if allocation_ids > 1:
                raise ValidationError(("Employee %s has duplicate daily allocation entry on date %s for shift %s") % (shift.employee_id.name, shift.date, shift.shift_id.name))

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = super(HrShiftDayofAllocation, self).create(vals_list)
        for vals in vals_list:
            vals.name = "%s-%s" %(vals.employee_id.name, vals.date)
        return vals_list
