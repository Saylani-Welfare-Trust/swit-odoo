from odoo import models


class AdvanceDonationStatementWizard(models.TransientModel):
    _inherit = 'advance.donation.statement.wizard'

    def _get_program_disbursements(self, df, dt, donor_id):
        lines, linked_line_ids = super()._get_program_disbursements(df, dt, donor_id)

        welfare_lines = self.env['welfare.line'].search([('advance_donation_line_id', '!=', False)])
        welfare_lines = welfare_lines.filtered(lambda r: self._keep_disbursement(r, df, dt, donor_id))
        micro_records = self.env['microfinance'].search([('advance_donation_line_id', '!=', False)])
        micro_records = micro_records.filtered(lambda r: self._keep_disbursement(r, df, dt, donor_id))

        # Lines already represented by a welfare / microfinance row (avoid
        # double counting).
        linked_line_ids |= set(welfare_lines.mapped('advance_donation_line_id').ids)
        linked_line_ids |= set(micro_records.mapped('advance_donation_line_id').ids)

        for w in welfare_lines:
            amount = self._pick_amount(w, [
                'advance_donation_amount', 'total_amount',
                'amount', 'disbursed_amount',
            ])
            if amount:
                lines.append(self._disbursement_line(
                    w, 'Welfare', amount,
                    w.welfare_id.display_name or '',
                    w.product_id.display_name or '',
                ))

        for m in micro_records:
            amount = self._pick_amount(m, [
                'advance_donation_amount', 'amount',
                'loan_amount', 'disbursed_amount',
            ])
            if amount:
                lines.append(self._disbursement_line(
                    m, 'Microfinance', amount,
                    m.display_name,
                    m.product_id.display_name or '',
                ))

        return lines, linked_line_ids
