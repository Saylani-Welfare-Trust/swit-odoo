from odoo import fields, models


class DonationBoxRequest(models.Model):
    _inherit = 'donation.box.request'


    key_ids = fields.One2many('key', 'donation_box_request_id', string='Key IDs')