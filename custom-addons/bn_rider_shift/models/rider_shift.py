from odoo import fields, models, api
from odoo.exceptions import UserError
from odoo.tools.translate import _

from datetime import timedelta

state_selection =[
    ('draft', 'Draft'),
    ('done', 'Done'),
]


class RiderShift(models.Model):
    _name = 'rider.shift'
    _description = 'Rider Shift'
    _inherit = ["mail.thread", "mail.activity.mixin"]


    rider_id = fields.Many2one('hr.employee', string="Rider", tracking=True)

    employee_category_id = fields.Many2one('hr.employee.category', string="Employee Category", default=lambda self: self.env.ref('bn_donation_box.donation_box_rider_hr_employee_category', raise_if_not_found=False).id)

    name = fields.Char('Name', default="New")

    start_date = fields.Date("Start Date", tracking=True)
    end_date = fields.Date("End Date", tracking=True)
    state= fields.Selection(selection=state_selection, default='draft', string="Status", tracking=True)
 
    schedule_day_ids = fields.One2many('rider.schedule.day', 'rider_shift_id', string="Schedule Days")


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('rider_shift_sequence') or ('New')

        return super(RiderShift, self).create(vals)
    
    def action_mark_done(self):
        for shift in self:
            if shift.state == 'draft':
                shift.state = 'done'
            else:
                raise UserError(_("Only shifts in 'Draft' state can be marked as 'Done'."))