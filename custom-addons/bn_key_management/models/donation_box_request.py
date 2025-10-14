from odoo import fields, models, api, exceptions


class DonationBoxRequest(models.Model):
    _inherit = 'donation.box.requests'


    key_ids = fields.One2many('key', 'donation_box_request_id', string='Key IDs')