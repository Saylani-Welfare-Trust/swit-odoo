from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from datetime import timedelta


class RiderShift(models.Model):
    _name = 'rider.shift'
    _description = 'Rider Shift'
    _inherit = ["mail.thread", "mail.activity.mixin"]


    rider_id = fields.Many2one('hr.employee', string="Rider", tracking=True)

    employee_category_id = fields.Many2one('hr.employee.category', string="Employee Category", default=lambda self: self.env.ref('bn_donation_box.donation_box_rider_hr_employee_category', raise_if_not_found=False).id)

    name = fields.Char(related='rider_id.name')

    start_date = fields.Date("Start Date", tracking=True)
    end_date = fields.Date("End Date", tracking=True)

    schedule_day_ids = fields.One2many('rider.schedule.day', 'rider_shift_id', string="Schedule Days")


    def action_generate_lines(self):
        for shift in self:
            if not shift.start_date or not shift.end_date:
                raise UserError(_("Start Date and End Date are required to generate lines."))
            
            start_date = fields.Date.to_date(shift.start_date)
            end_date = fields.Date.to_date(shift.end_date)
            
            if start_date > end_date:
                raise UserError(_("Start Date must be before End Date."))
            
            weekday_map = {
                0: 'mon',
                1: 'tue',
                2: 'wed',
                3: 'thu',
                4: 'fri',
                5: 'sat',
                6: 'sun',
            }
            
            # Remove existing schedule days
            shift.schedule_day_ids.unlink()
            
            lines_to_create = []
            current_date = start_date

            while current_date <= end_date:
                weekday = current_date.weekday()
                day_key = weekday_map.get(weekday)

                lines_to_create.append({
                    'rider_shift_id': shift.id,
                    'date': fields.Date.to_string(current_date),
                    'day': day_key,
                })
                
                current_date += timedelta(days=1)
            
            if lines_to_create:
                self.env['rider.schedule.day'].create(lines_to_create)
        
        return True