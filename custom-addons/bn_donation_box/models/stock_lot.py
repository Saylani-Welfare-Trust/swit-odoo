from odoo import models, fields


class StockLot(models.Model):
    _inherit = 'stock.lot'


    lot_consume = fields.Boolean('Lot Consume', default=False)
    is_not_return = fields.Boolean('Is not return', default=False)

    # Used by the city record rules of the rider models that only know the box.
    donation_box_registration_ids = fields.One2many(
        'donation.box.registration.installation', 'lot_id', string="Donation Box Registrations")
