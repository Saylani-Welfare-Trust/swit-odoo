from odoo import api, fields, models, _


class DonationItemModel(models.Model):
    _name = 'donation.item'
    _description = 'Donation Item'

    donation_type = fields.Char(string='Donation Type', tracking=True)
    donation_no = fields.Char(string='Donation No', tracking=True)
    type = fields.Char(string='Type', tracking=True)
    item = fields.Char(string='Item', tracking=True)
    is_priced_item = fields.Boolean(string='Is Priced Item', tracking=True)
    qty = fields.Float(string='QTY', tracking=True)
    price = fields.Float(string='Price', tracking=True)
    total = fields.Float(string='Total', tracking=True)
    price_id = fields.Char(string='Price Id', tracking=True)
    donation_data_id = fields.Many2one(comodel_name='donation.data', string='Donation Data')
