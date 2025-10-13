from odoo import fields, models, exceptions, api


class AccountMove(models.Model):
    _inherit = 'account.move'


    donation_api_id = fields.Many2one('donation.data', string="Donation API ID")