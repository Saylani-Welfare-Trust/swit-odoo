from odoo import models, fields


class DonationSlipUsage(models.Model):
    _name = 'advance.donation.slip.usage'


    advance_donation_id = fields.Many2one('advance.donation', string='Donation ID')
    donation_slip_id = fields.Many2one('advance.donation.receipt', string='Donation Slip')
    usage_amount = fields.Monetary('Usage Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', 'Currency',related='advance_donation_id.currency_id')
    
    # Related fields for better display
    receipt_date = fields.Date('Receipt Date', related='donation_slip_id.date', readonly=True)
    receipt_payment_type = fields.Selection([('cash', 'Cash'), ('cheque', 'Cheque')], string='Payment Type', related='donation_slip_id.payment_type', readonly=True)
    receipt_total_amount = fields.Monetary('Receipt Total Amount', related='donation_slip_id.amount', readonly=True)
