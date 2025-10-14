from odoo import fields, models, api, exceptions


class DonationBoxRequest(models.Model):
    _inherit = 'donation.box.registration'


    key_location_id = fields.Many2one('key.location', string="Key Location ID", tracking=True)