from odoo import models, fields, api
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
    ('paid', 'Paid')
]


class RiderCollection(models.Model):
    _name = 'rider.collection'
    _description = "Rider Collection"
    _rec_name = "box_no"


    lot_id = fields.Many2one('stock.lot', string="Lot")
    key_bunch_id = fields.Many2one('key.bunch', string="Key Bunch")
    rider_id = fields.Many2one('hr.employee', string="Rider")
    
    shop_name = fields.Char('Shop Name')
    box_location = fields.Char(string="Box Location")
    contact_person = fields.Char(string="Contact Person")
    contact_number = fields.Char(string="Contact Number")
    box_no = fields.Char(related='lot_id.name', string="Box No.")
    
    day = fields.Selection(selection=day_selection, string="Day", default='mon')
    state = fields.Selection(selection=state_selection, string="Status", default='donation_not_collected')
    
    date = fields.Date("Date")

    submission_time = fields.Datetime('Submission Date')

    amount = fields.Float('Amount')


    @api.model
    def get_rider_collection(self):
        # raise ValidationError('Hit')

        collection_ids = self.sudo().search([('state', '=', 'donation_submit')])

        if not collection_ids:
            return {
                "status": "error",
                "body": f"No donation collections were found for today {fields.Date.today().strftime('%d-%m-%Y')}."
            }

        # raise ValidationError(str(collection_ids))

        return {
            "status": "success",
            'collection_ids': [{
                'id': collection.id,
                'day': collection.day,
                'date': collection.date.strftime('%d-%m-%Y'),
                'lot_id': collection.lot_id.id if collection.lot_id else False,
                'box_no': collection.lot_id.name if collection.lot_id else '',
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