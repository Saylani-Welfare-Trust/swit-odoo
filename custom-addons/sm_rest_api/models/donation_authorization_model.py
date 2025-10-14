from odoo import fields, models, api, _


class DonationAuthorizationModel(models.Model):
    _name = 'donation.authorization'
    _description = 'Donation Authorization'
    _rec_name = 'url'

    url = fields.Char(string='URL', required=True)
    client_id = fields.Char(string='Client ID', required=True)
    client_secret = fields.Char(string='Client Secret', required=True)

