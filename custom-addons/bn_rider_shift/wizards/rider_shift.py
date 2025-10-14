from odoo import fields, models, api
from odoo.exceptions import UserError
from odoo.tools.translate import _


class RiderShiftWizard(models.TransientModel):
    _name = 'rider.shift.wizard'
    _description = 'Rider Shift Wizard'

    rider_shift_wizard_line_ids = fields.One2many('rider.shift.wizard.line', 'rider_shift_wizard_id', string="Rider Shift Wizard Line IDS")


    def action_check_shift(self):
        rider_shift_obj = self.env['schedule.day'].search([('rider_shift_id.rider_id', '=', self.env.user.employee_id.id), ('date', '=', fields.Date.today())])
        if not rider_shift_obj:
            raise UserError(_("No shift found for today. Please check your schedule."))
        line_vals = []

        for obj in rider_shift_obj:
            # raise UserError(str(obj.rider_shift_id.rider_id.name)+" <---> "+str(self.env.user.name))
            box_nos = obj.key_location_id.key_ids.mapped('box_no')
            box_location = self.env['donation.box.registration'].search([('box_no', 'in', box_nos)])
            # raise UserError(str(box_nos))
            line_vals.append((0, 0, {
                'day': obj.day,
                'date': obj.date,
                'city_id': obj.city_id.id,
                'zone_id': obj.zone_id.id,
                'sub_zone_id': obj.sub_zone_id.id,
                'key_location_id': obj.key_location_id.id,
                'box_location_name': box_location.location,
                'contact_person': box_location.contact_person_name,
                'contact_number': box_location.contact_no,
            }))

        rider_shift_wizard = self.env['rider.shift.wizard'].create({
            'rider_shift_wizard_line_ids': line_vals
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rider.shift.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_rider_shift.rider_shift_wizard_view_form').id,
            'res_id': rider_shift_wizard.id,
            'target': 'new'
        }
    

day_selection = [
    ('mon', 'Monday'),
    ('tue', 'Tuesday'),
    ('wed', 'Wednesday'),
    ('thu', 'Thursday'),
    ('fri', 'Friday'),
    ('sat', 'Saturday'),
    ('sun', 'Sunday'),
]


class RiderShiftWizard(models.TransientModel):
    _name = 'rider.shift.wizard.line'
    _description = 'Rider Shift Wizard Line'

    contact_person = fields.Char(string="Contact Person")
    contact_number = fields.Char(string="Contact Number")
    box_location_name = fields.Char(string="Box Location Name")
    rider_shift_wizard_id = fields.Many2one('rider.shift.wizard', string="Rider Shift Wizard ID")
    rider_id = fields.Many2one('hr.employee', string="Rider ID", default=lambda self: self.env.user.employee_id.id)
    
    day = fields.Selection(selection=day_selection, string="Day", default='mon')

    date = fields.Date("Date")

    city_id = fields.Many2one('res.company', string="City ID")
    zone_id = fields.Many2one('res.company', string="Zone ID")
    sub_zone_id = fields.Many2one('sub.zone', string="Sub Zone ID")
    key_location_id = fields.Many2one('key.location', string="Key Location ID")
