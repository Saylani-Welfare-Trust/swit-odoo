from odoo import models, fields, _


class AdvanceDonationLine(models.Model):
    _name = 'advance.donation.line'
    

    advance_donation_id = fields.Many2one('advance.donation', 'Donation ID')

    serial_no = fields.Char('Serial No.')
    product_id = fields.Many2one('product.product', 'Product')
    amount = fields.Monetary('Amount', currency_field='currency_id')

    paid_amount = fields.Monetary('Paid Amount', currency_field='currency_id')
    remaining_amount = fields.Monetary('Remaining Amount', currency_field='currency_id')

    state = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid')],
        string='Status', compute='_compute_installment_state')

    donation_state = fields.Selection([
        ('draft', 'Draft'),
        ('approval_1', 'Approval 1'),
        ('approval_2', 'Approval 2'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')],
        default='draft',
        string='Donation State', related='advance_donation_id.state')
    approved_date = fields.Datetime('Approved Date', related='advance_donation_id.approved_date')
    is_disbursed = fields.Boolean('Is Disbursed?')
    currency_id = fields.Many2one('res.currency', 'Currency', related='advance_donation_id.currency_id', readonly=True)


    def _compute_installment_state(self):
        for rec in self:
            if rec.paid_amount < rec.amount and rec.paid_amount != 0:
                rec.state = 'partial'
            elif rec.paid_amount == rec.amount:
                rec.state = 'paid'
            else:
                rec.state = 'unpaid'