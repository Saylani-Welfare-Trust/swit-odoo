from odoo import fields, models, api


day_selection = [
    ('mon', 'Monday'),
    ('tue', 'Tuesday'),
    ('wed', 'Wednesday'),
    ('thu', 'Thursday'),
    ('fri', 'Friday'),
    ('sat', 'Saturday'),
    ('sun', 'Sunday'),
]

class ScheduleDay(models.Model):
    _name = 'schedule.day'
    _description = 'Schedule Day'


    rider_shift_id = fields.Many2one('rider.shift', string="Rider Shift ID")

    day = fields.Selection(selection=day_selection, string="Day", default='mon')

    date = fields.Date("Date")

    city_id = fields.Many2one('res.company', string="City ID")
    zone_id = fields.Many2one('res.company', string="Zone ID", default=lambda self: self.env.company.id)
    sub_zone_id = fields.Many2one('sub.zone', string="Sub Zone ID")
    key_location_id = fields.Many2one('key.location', string="Key Location ID")

    name = fields.Char('Name', compute="_set_name")


    @api.depends('day', 'rider_shift_id')
    def _set_name(self):
        for record in self:
            record.name = ''

            if record.rider_shift_id:
                record.name = record.day.title() + ' ' + record.rider_shift_id.name