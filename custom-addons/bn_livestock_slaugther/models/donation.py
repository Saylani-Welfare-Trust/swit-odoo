from psycopg2 import IntegrityError

from odoo import models


class Donation(models.Model):
    _inherit = 'donation'

    def _get_livestock_department_vals(self, product):
        product_markers = ' '.join(filter(None, [
            product.display_name,
            product.default_code,
            product.product_tmpl_id.name,
            product.categ_id.complete_name,
        ])).lower()

        if 'goat' in product_markers:
            return {'is_goat_depart': True}
        if 'cow' in product_markers:
            return {'is_meat_depart': True}
        return {}

    def _create_livestock_slaughter_records(self):
        """An imported donation (from the Excel import) is already a
        settled bank transaction by the time it reaches Odoo - like a cash
        POS sale, there's no clearing step to wait for, so it falls into
        livestock right away."""
        slaughter_obj = self.env['livestock.slaugther'].sudo()

        for donation in self:
            product = donation.product_id
            if not product or not product.is_livestock:
                continue

            if slaughter_obj.search_count([('donation_id', '=', donation.id)]):
                continue

            slaughter_vals = {
                'product_id': product.id,
                'donee_id': donation.donor_id.id,
                'donation_id': donation.id,
                'quantity': 1,
                'price': donation.amount,
                'ref': donation.name,
            }
            slaughter_vals.update(donation._get_livestock_department_vals(product))

            try:
                with self.env.cr.savepoint():
                    slaughter_obj.create(slaughter_vals)
            except IntegrityError:
                continue


class ImportDonation(models.Model):
    _inherit = 'import.donation'

    def action_confirm(self):
        res = super().action_confirm()
        donations = self.env['donation'].search([('import_donation_id', 'in', self.ids)])
        donations._create_livestock_slaughter_records()
        return res
