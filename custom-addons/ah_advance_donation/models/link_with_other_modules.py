from odoo import models, fields, api

class MfdLoanReqeust(models.Model):
    _inherit = 'mfd.loan.request'

    advance_donation_line_id = fields.Many2one('ah.advance.donation.line')

    @api.onchange('product_id')
    def onchange_link_product_id(self):
        self.donor_contribution = 0
        advance_donation_id = self.env['ah.advance.donation'].search([
            ('product_id', '=', self.product_id.id),
            ('state', '=', 'approved'),
            ('is_fully_disbursed', '=', False)
        ], order='approved_date asc')

        advance_donation_line_id = advance_donation_id.advance_donation_lines.filtered(
            lambda line: line.is_disbursed == False
        )[:1]

        self.donor_contribution = advance_donation_line_id.amount

    @api.constrains('product_id')
    def constraints_link_product_id(self):
        self.donor_contribution = 0
        advance_donation_id = self.env['ah.advance.donation'].search([
            ('product_id', '=', self.product_id.id),
            ('state', '=', 'approved'),
            ('is_fully_disbursed', '=', False)
        ], order='approved_date asc', limit=1)

        advance_donation_line_id = advance_donation_id.advance_donation_lines.filtered(
            lambda line: line.is_disbursed == False
        )[:1]

        if advance_donation_line_id:
            self.donor_contribution = advance_donation_line_id.amount
            self.advance_donation_line_id = advance_donation_line_id.id
            advance_donation_line_id.write({'is_disbursed': True})

        if not advance_donation_line_id:
            if self.advance_donation_line_id:
                self.advance_donation_line_id.write({'is_disbursed': False})


    def action_rejected(self):
        if self.advance_donation_line_id:
            self.advance_donation_line_id.write({'is_disbursed': False})
        return super(MfdLoanReqeust, self).action_rejected()

    @api.ondelete(at_uninstall=False)
    def restrict_delete(self):
        for rec in self:
            if rec.advance_donation_line_id:
                rec.advance_donation_line_id.write({'is_disbursed': False})

