from odoo import models, fields, api


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


class RiderCollection(models.Model):
    _name = 'rider.collection'
    _description = "Rider Collection"
    _rec_name = "shop_name"

    counterfeit_note_ids = fields.Many2many(
        'counterfeit.notes',
        'rider_collection_counterfeit_rel',
        'collection_id',
        'note_id',
        string='Counterfeit Notes'
    )

    rider_id = fields.Many2one('hr.employee', string="Rider")
    donation_box_registration_installation_id = fields.Many2one('donation.box.registration.installation', string="Donation Box")

    shop_name = fields.Char(related='donation_box_registration_installation_id.shop_name', string="Shop Name", store=True)
    contact_person = fields.Char(related='donation_box_registration_installation_id.contact_person', string="Contact Person", store=True)
    contact_number = fields.Char(related='donation_box_registration_installation_id.contact_no', string="Contact Number", store=True)
    box_location = fields.Char(related='donation_box_registration_installation_id.location', string="Box Location", store=True)

    lot_id = fields.Many2one(related='donation_box_registration_installation_id.lot_id', string="Box No.", store=True)
    key_bunch_id = fields.Many2one(related='donation_box_registration_installation_id.key_bunch_id', string="Key Bunch", store=True)
    sub_zone_id = fields.Many2one(related='donation_box_registration_installation_id.sub_zone_id', string="Sub Zone", store=True)
    
    day = fields.Selection(selection=day_selection, string="Day", default='mon')
    state = fields.Selection(selection=state_selection, string="Status", default='donation_not_collected')

    is_complain_generated = fields.Boolean('Is Complain Generated', default=False)
    
    date = fields.Date("Date")

    submission_time = fields.Date('Submission Date')

    amount = fields.Float('Amount')
    foreign_notes = fields.Float('Foreign Currency')
    counterfeit_notes = fields.Float('Counterfeit Notes')

    remarks = fields.Text('Remarks')
    foreign_currency_line_ids = fields.Many2many(
        'foreign.currency',
        'rider_collection_foreign_currency_rel',
        'collection_id',
        'foreign_currency_id',
        string='Foreign Currency Lines'
    )

    is_fcb = fields.Boolean('Is FCB', compute='_compute_is_fcb')
    
    def _compute_is_fcb(self):
        for record in self:
            record.is_fcb = record.remarks == 'FCB'
    
    def action_mark_cfb_paid(self):
        """Mark all linked counterfeit notes as paid"""
        for collection in self:
            if collection.remarks == 'CFB' and collection.counterfeit_note_ids:
                collection.counterfeit_note_ids.write({'state': 'payment_received'})
                collection.state = 'paid'
        return True

    @api.model
    def get_rider_collection(self):
        collection_ids = self.sudo().search([('state', '=', 'donation_submit')])

        if not collection_ids:
            return {
                "status": "error",
                "body": f"No donation collections were found for today {fields.Date.today().strftime('%d-%m-%Y')}."
            }

        return {
            "status": "success",
            'collection_ids': [{
                'id': collection.id,
                'day': collection.day,
                'date': collection.date,
                'lot_id': collection.lot_id.id if collection.lot_id else False,
                'box_no': collection.remarks or (collection.lot_id.name if collection.lot_id else ''),
                'shop_name': collection.shop_name,
                'contact_person': collection.contact_person,
                'contact_number': collection.contact_number,
                'box_location': collection.box_location,
                'amount': collection.amount,
                'rider_id': collection.rider_id.id
            } for collection in collection_ids],
            'rider_ids': [
                {'id': rider.id, 'name': rider.name}
                for rider in collection_ids.mapped('rider_id')
            ]
        }
    