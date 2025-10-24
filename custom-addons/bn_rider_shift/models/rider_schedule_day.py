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

class RiderScheduleDay(models.Model):
    _name = 'rider.schedule.day'
    _description = 'Rider Schedule Day'


    rider_shift_id = fields.Many2one('rider.shift', string="Rider Shift")

    day = fields.Selection(selection=day_selection, string="Day", default='mon')

    date = fields.Date("Date")

    city_id = fields.Many2one('account.analytic.account', string="City")
    zone_id = fields.Many2one('account.analytic.account', string="Zone")
    key_bunch_id = fields.Many2one('key.bunch', string="Key Bunch")
    sub_zone_id = fields.Many2one('sub.zone', string="Sub Zone", tracking=True)

    name = fields.Char('Name', compute="_set_name")


    @api.depends('day', 'rider_shift_id')
    def _set_name(self):
        for record in self:
            record.name = ''

            if record.rider_shift_id:
                record.name = record.day.title() + ' ' + record.rider_shift_id.name