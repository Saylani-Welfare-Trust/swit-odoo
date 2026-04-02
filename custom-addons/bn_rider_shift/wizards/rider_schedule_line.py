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

box_status_selection = [
    ('missing', 'Missing'),
    ('broken', 'Broken'),
    ('robbery', 'Robbery'),
    ('return', 'Return'),
    ('repaired', 'Repaired'),
]


class RiderScheduleLine(models.TransientModel):
    _name = 'rider.schedule.line'
    _description = 'Rider Shift Line'


    donation_box_registration_installation_id = fields.Many2one('donation.box.registration.installation', string="Donation Box")

    shop_name = fields.Char(related='donation_box_registration_installation_id.shop_name', string="Shop Name", store=True)
    contact_person = fields.Char(related='donation_box_registration_installation_id.contact_person', string="Contact Person", store=True)
    contact_number = fields.Char(related='donation_box_registration_installation_id.contact_no', string="Contact Number", store=True)
    box_location = fields.Char(related='donation_box_registration_installation_id.location', string="Box Location", store=True)

    lot_id = fields.Many2one(related='donation_box_registration_installation_id.lot_id', string="Box No.", store=True)
    rider_collection_id = fields.Many2one('rider.collection', string="Rider Collection")
    rider_schedule_id = fields.Many2one('rider.schedule', string="Rider Schedule")
    rider_id = fields.Many2one('hr.employee', string="Rider")
    key_bunch_id = fields.Many2one(related='donation_box_registration_installation_id.key_bunch_id', string="Key Bunch", store=True)
    sub_zone_id = fields.Many2one(related='donation_box_registration_installation_id.sub_zone_id', string="Sub Zone", store=True)

    day = fields.Selection(selection=day_selection, string="Day", default='mon')
    state = fields.Selection(selection=state_selection, string="Status", default='donation_not_collected')
    box_status = fields.Selection(selection=box_status_selection, string="Box Status")
    
    date = fields.Date('Date')

    submission_time = fields.Date('Submission Date')

    amount = fields.Float('Amount')
    foreign_notes = fields.Float('Foreign Notes')
    counterfeit_notes = fields.Float('Counter Feit Notes')

    remarks = fields.Text('Remarks')


    def mark_as_done(self):
        self.state = 'donation_collected'
        self.rider_collection_id.state = 'donation_collected'

        # return {
        #     'type': 'ir.actions.act_window',
        #     'res_model': 'rider.schedule',
        #     'view_mode': 'form',
        #     'view_id': self.env.ref('bn_rider_shift.rider_schedule_view_form').id,
        #     'res_id': self.rider_schedule_id.id,
        #     'target': 'current'
        # }
    
    def mark_as_pending(self):
        if not self.remarks:
            raise ValidationError('Please enter the remarks first.')

        self.state = 'pending'
        self.rider_collection_id.state = 'pending'
        self.rider_collection_id.amount = self.amount
        self.rider_collection_id.foreign_notes = self.foreign_notes
        self.rider_collection_id.counterfeit_notes = self.counterfeit_notes
        self.rider_collection_id.remarks = self.remarks
        key = self.env['key'].search([('lot_id', '=', self.lot_id.id)], limit=1)

        key.state = 'pending'

        key_issuance = self.env['key.issuance'].search([('issue_date', '=', self.date), ('lot_id', '=', self.lot_id.id), ('key_id', '=', key.id), ('state', 'in', ['issued', 'overdue'])], limit=1)

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
        self.rider_collection_id.foreign_notes = self.foreign_notes
        self.rider_collection_id.counterfeit_notes = self.counterfeit_notes
        self.rider_collection_id.remarks = self.remarks
        self.env['counterfeit.notes'].create({
            'rider_id': self.rider_id.id,
            'lot_id': self.lot_id.id,
            'submission_time': self.submission_time,
            'amount': self.counterfeit_notes,
            # 'foreign_notes': self.foreign_notes,
            # 'counterfeit_notes': self.counterfeit_notes,
            # 'remarks': self.remarks,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rider.schedule',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_rider_shift.rider_schedule_view_form').id,
            'res_id': self.rider_schedule_id.id,
            'target': 'current'
        }
        
    def action_generate_complain(self):
        # raise ValidationError(self.donation_box_registration_installation_id.id)

        if not self.remarks:
            raise ValidationError('Please enter the remarks first.')
        
        if not self.box_status:
            raise ValidationError('Please select the box status first.')

        self.env['donation.box.complain.center'].create({
            'rider_id': self.rider_id.id,
            'lot_id': self.lot_id.id,
            'date': fields.Date.today(),
            'box_status': self.box_status,
            'remarks': self.remarks,
        })
        
        # Mark the related rider collection as complain generated
        if self.rider_collection_id:
            self.rider_collection_id.is_complain_generated = True

    def action_change_rate(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Foreign Currency Lines',
            'res_model': 'foreign.currency.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.rider_collection_id.id if self.rider_collection_id else False,
            }
        }
        
        