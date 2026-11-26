from odoo import api, models


class DonationHomeService(models.Model):
    _inherit = 'donation.home.service'

    def _create_livestock_slaughter_records(self):
        """A Donation Home Service falls into livestock once it is Paid (at the POS,
        or by a cleared Direct Deposit): one record per animal of its livestock
        lines. The POS order / Direct Deposit that paid it makes none for them."""
        slaughter_obj = self.env['livestock.slaugther'].sudo()

        for service in self.sudo().filtered(lambda s: s.state == 'paid'):
            livestock_lines = service.donation_home_service_line_ids.filtered(
                lambda line: line.product_id.is_livestock and line.quantity > 0
            )
            for line in livestock_lines:
                vals = {
                    'product_id': line.product_id.id,
                    'donee_id': service.donor_id.id,
                    'ref': service.name,
                    # the POS order / session / POS it was booked and paid at
                    **service._pos_link_vals(),
                }
                vals.update(self.env['pos.order']._get_livestock_department_vals(line.product_id))
                # line.amount is the unit price
                slaughter_obj._create_for_source(
                    'dhs_line_id', line, line.quantity, line.amount * line.quantity, vals)

    @api.model_create_multi
    def create(self, vals_list):
        services = super().create(vals_list)
        services._create_livestock_slaughter_records()
        return services

    def write(self, vals):
        paying = self.filtered(lambda s: s.state != 'paid') if vals.get('state') == 'paid' else self.browse()
        result = super().write(vals)
        paying._create_livestock_slaughter_records()
        return result
