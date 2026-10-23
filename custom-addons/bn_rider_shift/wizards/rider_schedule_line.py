from odoo import models, fields, _
from odoo.exceptions import AccessError, ValidationError


state_selection = [
    ('donation_not_collected', 'Donation not collected'),
    ('donation_collected', 'Donation collected'),
    ('donation_submit', 'Donation submit'),
    ('pending', 'Pending'),
    ('paid', 'Paid')
]

RIDER_USER_GROUP = 'bn_rider_shift.rider_shift_user_group'
RIDER_MANAGER_GROUP = 'bn_rider_shift.rider_shift_manager_group'
OPEN_COLLECTION_STATES = ('donation_not_collected', 'donation_collected')

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

    is_complain_generated = fields.Boolean(string="Complaint Generated", default=False)
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

    state = fields.Selection(selection=state_selection, string="Status", default='donation_not_collected')
    box_status = fields.Selection(selection=box_status_selection, string="Box Status")
    
    date = fields.Date('Date')

    submission_time = fields.Date('Submission Date')

    amount = fields.Float('Amount')
    foreign_notes = fields.Float('Foreign Notes')
    counterfeit_notes = fields.Float('Counter Feit Notes')

    remarks = fields.Text('Remarks')


    def _own_collection(self, open_only=True):
        """The rider's own open collection, as superuser.

        Riders report their collection here (My Schedule): the amount they
        enter is written to the collection even though only the "Edit Amount /
        Notes" group may change it on the collection itself. Only the rider of
        the collection (or a Rider Shift Manager) may do so, and only while the
        collection is still open."""
        self.ensure_one()
        user = self.env.user
        if not self.env.su:
            if not user.has_group(RIDER_USER_GROUP):
                raise AccessError(_('Only Rider Shift users can report a collection.'))
            if self.rider_id not in user.employee_ids and not user.has_group(RIDER_MANAGER_GROUP):
                raise AccessError(_('You can only report your own collections.'))
        collection = self.rider_collection_id.sudo()
        if not collection:
            raise ValidationError(_('This line has no rider collection.'))
        if open_only and collection.state not in OPEN_COLLECTION_STATES:
            raise ValidationError(_('Collection of box "%s" was already submitted or marked pending.')
                                  % self.lot_id.display_name)
        return collection

    def mark_as_done(self):
        collection = self._own_collection()
        self.state = 'donation_collected'
        collection.state = 'donation_collected'

    def mark_as_pending(self):
        if not self.remarks:
            raise ValidationError('Please enter the remarks first.')
        collection = self._own_collection()

        self.state = 'pending'
        collection.write({
            'state': 'pending',
            'amount': self.amount,
            'foreign_notes': self.foreign_notes,
            'counterfeit_notes': self.counterfeit_notes,
            'remarks': self.remarks,
        })

        # The key of this line's own registration: a reused box number also has
        # the closed keys of its earlier registrations.
        # Key Management records: read and updated as superuser (checked above).
        key = self.env['key'].sudo().search([
            ('donation_box_registration_installation_id', '=', self.donation_box_registration_installation_id.id),
            ('state', '!=', 'closed'),
        ], order='id desc', limit=1)
        if not key:
            raise ValidationError('No key in service found for box "%s".' % self.lot_id.display_name)

        key_issuance = self.env['key.issuance'].sudo().search([
            ('issue_date', '=', self.date), ('lot_id', '=', self.lot_id.id),
            ('key_id', '=', key.id), ('state', 'in', ['issued', 'overdue']),
        ], limit=1)
        if not key_issuance:
            raise ValidationError('No active issuance found for box "%s" on %s.' % (self.lot_id.display_name, self.date))

        # Goes through the guarded workflow method (checks state, keeps key.state in
        # sync with the issuance) instead of writing .state directly on both records.
        key_issuance.action_pending()
    
    def mark_as_submit(self):
        if self.amount < 0:
            raise ValidationError('Please first enter the valid collected amount.')
        if self.counterfeit_notes < 0:
            raise ValidationError('Please first enter the valid Counterfeit Notes amount.')
        collection = self._own_collection()

        self.state = 'donation_submit'
        self.submission_time = fields.Datetime.now()
        collection.write({
            'state': 'donation_submit',
            'submission_time': fields.Datetime.now(),
            'amount': self.amount,
            'foreign_notes': self.foreign_notes,
            'counterfeit_notes': self.counterfeit_notes,
            'remarks': self.remarks,
        })
        
        if self.counterfeit_notes > 0:
            self.env['counterfeit.notes'].create({
                'rider_id': self.rider_id.id,
                'lot_id': self.lot_id.id,
                'submission_time': self.submission_time,
                'amount': self.counterfeit_notes,
            })
        
    def action_generate_complain(self):
        if not self.remarks:
            raise ValidationError('Please enter the remarks first.')
        
        if not self.box_status:
            raise ValidationError('Please select the box status first.')
        collection = self._own_collection(open_only=False)

        # Donation Box record: created as superuser (rider checked above); it
        # waits in Draft for the Complain Center.
        complaint = self.env['donation.box.complain.center'].sudo().create({
            'donation_box_registration_installation_id': self.donation_box_registration_installation_id.id,
            'rider_id': self.rider_id.id,
            'lot_id': self.lot_id.id,
            'date': fields.Date.today(),
            'box_status': self.box_status,
            'remarks': self.remarks,
        })
        # Stays in Draft (the model's own default). It is only moved to Process
        # by an explicit follow-up action - the Complain Officer's "Process"
        # button on the complaint's own form - never advanced automatically
        # here. The registration itself is only closed later still, when the
        # complaint is fully resolved.

        # Hide button after complaint generation
        self.is_complain_generated = True

        # Mark related rider collection
        collection.is_complain_generated = True

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
        
        