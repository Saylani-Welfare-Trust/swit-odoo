from odoo import models


class AdvanceDonationSync(models.Model):
    """A livestock contract puts its animals into Livestock Slaughter once approved."""
    _inherit = 'advance.donation'

    def action_approved(self):
        res = super().action_approved()
        self.filtered(lambda d: d.state == 'approved')._create_livestock_slaughter_records()
        return res

    def _create_livestock_slaughter_records(self):
        """Each livestock line of an approved contract gets one Livestock Slaughter
        record per animal, funded by that line (which is then reserved for them).
        The line is disbursed when its animals are slaughtered (livestock.slaugther
        action_confirm). Open contracts are an amount, not a number of animals:
        they are linked by hand (Select Advance Donation). Run again, it creates
        nothing more."""
        Slaughter = self.env['livestock.slaugther'].sudo()
        department_vals = self.env['pos.order']._get_livestock_department_vals
        for donation in self.filtered(lambda d: d.state == 'approved' and d.contract_type != 'open_contract'):
            lines = donation.advance_donation_lines.filtered(
                lambda l: l.product_id.is_livestock and l.quantity > 0
                and not l.is_reserved and not l.reserved_amount)
            for line in lines:
                vals = {
                    'product_id': line.product_id.id,
                    'donee_id': donation.donor_id.id,
                    'ref': donation.name,
                    'advance_donation_id': donation.id,
                    **department_vals(line.product_id),
                }
                records = Slaughter._create_for_source(
                    'advance_donation_line_id', line, line.quantity, line.amount, vals)
                for record in records:
                    record.advance_donation_amount = record.price
                line.write({'is_reserved': True, 'reserved_amount': line.amount})
