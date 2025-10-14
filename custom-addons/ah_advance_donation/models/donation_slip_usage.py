from odoo import fields,api,models,_
from odoo.exceptions import UserError

class DonationSlipUsage(models.Model):
    _name = 'advance.donation.slip.usage'

    advance_donation_id = fields.Many2one('ah.advance.donation', string='Donation ID')
    donation_slip_id = fields.Many2one('ah.advance.donation.receipt', string='Donation Slip')
    usage_amount = fields.Monetary('Usage Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', 'Currency',related='advance_donation_id.currency_id')
