from odoo import models


class AdvanceDonationStatementWizard(models.AbstractModel):
    _inherit = 'advance.donation.statement.wizard'

    def _disbursement_donees(self, rec):
        # recurring lines register their disbursement on the welfare only
        return super()._disbursement_donees(rec) | rec.welfare_id.donee_id

    def _disbursement_purpose(self, rec):
        if rec.welfare_line_id:
            return 'Welfare'
        if rec.welfare_id:
            return 'Welfare (Recurring)'
        return super()._disbursement_purpose(rec)

    def _get_program_disbursements(self, df, dt, donor_id):
        lines, linked_line_ids = super()._get_program_disbursements(df, dt, donor_id)
        donor_domain = ([('advance_donation_line_id.advance_donation_id.donor_id', '=', donor_id)]
                        if donor_id else [('advance_donation_line_id', '!=', False)])

        # Program records are read as superuser: a statement user (Advance
        # Donation group) may have no Welfare / Microfinance access, and only
        # the records using this donor's donation lines are read.
        env = self.sudo().env

        # Welfare lines are listed from their disbursement records once paid.
        # A line linked to a donation line is only reserved until then, and
        # lines paid before those records were kept are listed here.
        recorded = env['advance.donation.disbursement.line'].search(
            [('welfare_line_id', '!=', False)]).welfare_line_id
        welfare_lines = env['welfare.line'].search(donor_domain + [
            ('state', 'in', ('disbursed', 'collected')),
            ('id', 'not in', recorded.ids),
        ]).filtered(lambda r: self._keep_disbursement(r, df, dt, donor_id))

        micro_records = env['microfinance'].search(donor_domain).filtered(
            lambda r: self._keep_disbursement(r, df, dt, donor_id))

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
                donee = w.welfare_id.donee_id
                lines.append(self._disbursement_line(
                    w, 'Welfare', amount,
                    donee.name or w.welfare_id.display_name or '',
                    w.product_id.display_name or '',
                    donees=donee,
                    rec_date=self._rec_date(w, ('collection_date', 'write_date')),
                ))

        for m in micro_records:
            amount = self._pick_amount(m, [
                'advance_donation_amount', 'amount',
                'loan_amount', 'disbursed_amount',
            ])
            if amount:
                lines.append(self._disbursement_line(
                    m, 'Microfinance', amount,
                    m.donee_id.name or m.display_name,
                    m.product_id.display_name or '',
                    donees=m.donee_id,
                    rec_date=self._rec_date(m, ('delivery_date', 'create_date')),
                ))

        return lines, linked_line_ids
