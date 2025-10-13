from odoo import models, fields


day_selection = [
    ('mon', 'Monday'),
    ('tue', 'Tuesday'),
    ('wed', 'Wednesday'),
    ('thu', 'Thursday'),
    ('fri', 'Friday'),
    ('sat', 'Saturday'),
    ('sun', 'Sunday'),
]

state_selection = [
    ('donation_not_collected', 'Donation not collected'),
    ('donation_collected', 'Donation collected'),
    ('donation_submit', 'Donation submit'),
    ('paid', 'Paid')
]


class RiderCollection(models.Model):
    _name = 'rider.collection'
    _description = "Rider Collection"
    _rec_name = "box_no"


    box_no = fields.Char('Box No.')
    shop_name = fields.Char('Shop Name')
    contact_person = fields.Char(string="Contact Person")
    contact_number = fields.Char(string="Contact Number")
    box_location_name = fields.Char(string="Box Location Name")
    
    city_id = fields.Many2one('res.company', string="City ID")
    zone_id = fields.Many2one('res.company', string="Zone ID")
    sub_zone_id = fields.Many2one('sub.zone', string="Sub Zone ID")
    key_location_id = fields.Many2one('key.location', string="Key Location ID", tracking=True)
    rider_id = fields.Many2one('hr.employee', string="Rider ID", default=lambda self: self.env.user.employee_id.id)
    
    day = fields.Selection(selection=day_selection, string="Day", default='mon')
    state = fields.Selection(selection=state_selection, string="Status", default='donation_not_collected')
    
    date = fields.Date("Date")

    submission_time = fields.Datetime(string="Submission Date")

    amount = fields.Float('Amount')