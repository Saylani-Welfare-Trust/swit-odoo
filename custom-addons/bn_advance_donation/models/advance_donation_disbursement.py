from odoo import models, fields

class AdvanceDonationDisbursementLine(models.Model):
    _name = 'advance.donation.disbursement.line'
    _description = 'Advance Donation Disbursement Line'

    advance_donation_id = fields.Many2one('advance.donation', string="Advance Donation")
    advance_donation_line_id = fields.Many2one('advance.donation.lines', string="Donation Line", ondelete='cascade',)

    product_id = fields.Many2one('product.product', string="Product")
    date = fields.Date(string="Date")

    total_amount = fields.Float(string="Total Amount")  # before deduction
    advance_amount = fields.Float(string="Advance Donation Amount")
    disbursed_amount = fields.Float(string="Final Disbursed Amount")

    # Program modules add their own link fields (bn_welfare: welfare_id,
    # welfare_line_id; bn_microfinance: microfinance_id) for traceability.
    disbursed_record= fields.Char(string="Disbursed Record", help="Reference to the record where this disbursement is recorded (e.g., welfare line, microfinance record)")
    
    def action_print_line_non_cash_disbursement_report(self):
        """Print the disbursement certificate for the given line(s)"""
        return self.env.ref('bn_advance_donation.action_report_advance_donation_disbursement_line').report_action(self)

    def _get_receipt_groups(self):
        """Lines with the same product and date are merged into one certificate item"""
        groups = {}
        for line in self.sorted('id'):
            key = (line.product_id.id, line.date)
            groups[key] = groups.get(key, self.browse()) | line
        return list(groups.values())

    def _get_donees(self):
        """Beneficiaries of these lines, extended by the program modules."""
        return self.env['res.partner']

    def _get_source_links(self):
        """[(label, name)] of the records these lines were disbursed for,
        extended by the program modules."""
        return []
