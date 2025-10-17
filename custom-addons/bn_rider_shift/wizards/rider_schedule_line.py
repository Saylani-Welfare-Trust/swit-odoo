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


class RiderScheduleLine(models.TransientModel):
    _name = 'rider.schedule.line'
    _description = 'Rider Shift Line'


    shop_name = fields.Char('Shop Name')
    contact_person = fields.Char(string="Contact Person")
    contact_number = fields.Char(string="Contact Number")
    box_location = fields.Char(string="Box Location")

    lot_id = fields.Many2one('stock.lot', string="Box No.")
    rider_collection_id = fields.Many2one('rider.collection', string="Rider Collection")
    rider_schedule_id = fields.Many2one('rider.schedule', string="Rider Schedule")
    rider_id = fields.Many2one('hr.employee', string="Rider")
    key_bunch_id = fields.Many2one('key.bunch', string="Key Bunch")

    day = fields.Selection(selection=day_selection, string="Day", default='mon')
    state = fields.Selection(selection=state_selection, string="Status", default='donation_not_collected')
    
    date = fields.Date('Date')

    submission_time = fields.Datetime('Submission Date')

    amount = fields.Float('Amount')


    def mark_as_done(self):
        self.state = 'donation_collected'
        self.rider_collection_id.state = 'donation_collected'
    
    def mark_as_submit(self):
        self.state = 'donation_submit'
        self.submission_time = fields.Datetime.now()
        self.rider_collection_id.state = 'donation_submit'
        self.rider_collection_id.submission_time = fields.Datetime.now()
        self.rider_collection_id.amount = self.amount