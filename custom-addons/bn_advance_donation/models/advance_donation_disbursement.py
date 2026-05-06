from odoo import models, fields

class AdvanceDonationDisbursementLine(models.Model):
    _name = 'advance.donation.disbursement.line'
    _description = 'Advance Donation Disbursement Line'

    advance_donation_id = fields.Many2one('advance.donation', string="Advance Donation")
    advance_donation_line_id = fields.Many2one('advance.donation.line', string="Donation Line")

    product_id = fields.Many2one('product.product', string="Product")
    date = fields.Date(string="Date")

    total_amount = fields.Float(string="Total Amount")  # before deduction
    advance_amount = fields.Float(string="Advance Donation Amount")
    disbursed_amount = fields.Float(string="Final Disbursed Amount")

    # Optional linking (for traceability)
    welfare_id = fields.Many2one('welfare')
    welfare_line_id = fields.Many2one('welfare.line')
    # recurring_line_id = fields.Many2one('welfare.recurring.line')
    microfinance_id = fields.Many2one('microfinance')
    disbursed_record= fields.Char(string="Disbursed Record", help="Reference to the record where this disbursement is recorded (e.g., welfare line, microfinance record)")
    
    def action_print_line_non_cash_disbursement_report(self):
        """Print non-cash donation report for this specific line"""
        return self.env.ref('bn_advance_donation.action_report_advance_donation_disbursement_line').report_action(self)