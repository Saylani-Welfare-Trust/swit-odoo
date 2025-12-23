from odoo import models, fields
from odoo.exceptions import ValidationError


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
    ('pending', 'Pending'),
    ('paid', 'Paid')
]


class RiderScheduleLine(models.TransientModel):
    _name = 'rider.schedule.line'
    _description = 'Rider Shift Line'


    shop_name = fields.Char('Shop Name')
    contact_person = fields.Char('Contact Person')
    contact_number = fields.Char('Contact Number')
    box_location = fields.Char(string="Box Location")

    lot_id = fields.Many2one('stock.lot', string="Box No.")
    rider_collection_id = fields.Many2one('rider.collection', string="Rider Collection")
    rider_schedule_id = fields.Many2one('rider.schedule', string="Rider Schedule")
    rider_id = fields.Many2one('hr.employee', string="Rider")
    key_bunch_id = fields.Many2one('key.bunch', string="Key Bunch")

    day = fields.Selection(selection=day_selection, string="Day", default='mon')
    state = fields.Selection(selection=state_selection, string="Status", default='donation_not_collected')
    
    date = fields.Date('Date')

    submission_time = fields.Date('Submission Date')

    amount = fields.Float('Amount')
    counterfeit_notes = fields.Float('Counter Feit Notes')

    remarks = fields.Text('Remarks')


    def mark_as_done(self):
        self.state = 'donation_collected'
        self.rider_collection_id.state = 'donation_collected'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rider.schedule',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_rider_shift.rider_schedule_view_form').id,
            'res_id': self.rider_schedule_id.id,
            'target': 'current'
        }
    
    def mark_as_pending(self):
        if not self.remarks:
            raise ValidationError('Please enter the remarks first.')

        self.state = 'pending'
        self.rider_collection_id.state = 'pending'
        self.rider_collection_id.remarks = self.remarks

        key = self.env['key'].search([('lot_id', '=', self.lot_id.id)], limit=1)

        key.state = 'pending'

        key_issuance = self.env['key.issuance'].search([('issue_date', '=', self.date), ('lot_id', '=', self.lot_id.id), ('key_id', '=', key.id), ('state', '=', 'issued')], limit=1)

        key_issuance.state = 'pending'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rider.schedule',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_rider_shift.rider_schedule_view_form').id,
            'res_id': self.rider_schedule_id.id,
            'target': 'current'
        }
    
    def mark_as_submit(self):
        if self.amount < 0:
            raise ValidationError('Please first enter the valid collected amount.')
        if self.counterfeit_notes < 0:
            raise ValidationError('Please first enter the valid Counterfeit Notes amount.')

        self.state = 'donation_submit'
        self.submission_time = fields.Datetime.now()
        self.rider_collection_id.state = 'donation_submit'
        self.rider_collection_id.submission_time = fields.Datetime.now()
        self.rider_collection_id.amount = self.amount
        self.rider_collection_id.counterfeit_notes = self.counterfeit_notes

        self.env['counterfeit.notes'].create({
            'rider_id': self.rider_id.id,
            'lot_id': self.lot_id.id,
            'submission_time': self.submission_time,
            'amount': self.counterfeit_notes,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rider.schedule',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_rider_shift.rider_schedule_view_form').id,
            'res_id': self.rider_schedule_id.id,
            'target': 'current'
        }