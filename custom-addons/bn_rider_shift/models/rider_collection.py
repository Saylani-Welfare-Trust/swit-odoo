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
                'box_no': collection.lot_id.name if collection.lot_id else '',
                'shop_name': collection.shop_name,
                'contact_person': collection.contact_person,
                'contact_number': collection.contact_number,
                'box_location': collection.box_location,
                'amount': collection.amount,
                'date': collection.date,
                'rider_id': collection.rider_id.id
            } for collection in collection_ids],
            'rider_ids': [
                {'id': rider.id, 'name': rider.name}
                for rider in collection_ids.mapped('rider_id')
            ]
        }
    