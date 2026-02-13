from odoo import models, fields, api, _
from datetime import date as td


class AdvanceDonationLine(models.Model):
    _name = 'advance.donation.line'
    

    advance_donation_id = fields.Many2one('advance.donation', 'Donation ID')

    serial_no = fields.Char('Serial No.')
    product_id = fields.Many2one('product.product', 'Product')
    amount = fields.Monetary('Amount', currency_field='currency_id')

    paid_amount = fields.Monetary('Paid Amount', currency_field='currency_id')
    remaining_amount = fields.Monetary('Remaining Amount', currency_field='currency_id')
    disbursed_amount = fields.Monetary('Disbursed Amount', currency_field='currency_id')    
    state = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid')],
        string='Status', compute='_compute_installment_state', store=True)

    donation_state = fields.Selection([
        ('draft', 'Draft'),
        ('approval_1', 'Approval 1'),
        ('approval_2', 'Approval 2'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')],
        default='draft',
        string='Donation State', related='advance_donation_id.state')
    approved_date = fields.Datetime('Approved Date', related='advance_donation_id.approved_date')
    is_disbursed = fields.Boolean('Is Disbursed?', compute='_compute_disbursement_and_disbursed')
    currency_id = fields.Many2one('res.currency', 'Currency', related='advance_donation_id.currency_id', readonly=True)

    date = fields.Date(
        string='Date',
        help='Date of this line (visible if contract type is frequency based)',
    )
    disbursement_date = fields.Date(
        string='Disbursement Date',
        compute='_compute_disbursement_and_disbursed',
        help='Date when the disbursement is made'
    )

    date_visibility = fields.Boolean(
        string='Date Visibility',
        help='Controls the visibility of the date field in the tree view. It is set to True if the contract type is frequency based, otherwise False.',
        compute='_compute_date_visibility'
    )

    @api.depends('disbursed_amount', 'paid_amount')
    def _compute_disbursement_and_disbursed(self):
        for rec in self:
            is_disbursed = rec.disbursed_amount == rec.paid_amount and rec.paid_amount != 0
            rec.is_disbursed = is_disbursed
            if is_disbursed:
                rec.disbursement_date = td.today()
            else:
                rec.disbursement_date = False
    
    @api.depends('advance_donation_id.contract_type')
    def _compute_date_visibility(self):
        for rec in self:
            if rec.advance_donation_id.contract_type == 'frequency':
                rec.date_visibility = True
            else: rec.date_visibility = False
    
    
    @api.depends('paid_amount', 'amount')
    def _compute_installment_state(self):
        for rec in self:
            if rec.paid_amount < rec.amount and rec.paid_amount != 0:
                rec.state = 'partial'
            elif rec.paid_amount == rec.amount:
                rec.state = 'paid'
            else:
                rec.state = 'unpaid'
    
    def action_print_line_non_cash_report(self):
        """Print non-cash donation report for this specific line"""
        return self.env.ref('bn_advance_donation.action_report_advance_donation_line_non_cash').report_action(self)