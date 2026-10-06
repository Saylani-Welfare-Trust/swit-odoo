from psycopg2 import IntegrityError

from odoo import models


class APIDonation(models.Model):
    _inherit = 'api.donation'

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

    def _create_livestock_slaughter_records(self, gateway_config):
        """An API donation is already confirmed by the payment gateway
        (status == 'success') by the time it's fetched into Odoo - like a
        cash POS sale, there's no clearing step to wait for, so it falls
        into livestock right away. Product resolution mirrors the stock
        resolution done in api.donation.wizard._process_donations_bulk()."""
        slaughter_obj = self.env['livestock.slaugther'].sudo()
        if not gateway_config:
            return

        for donation in self:
            for item in donation.donation_item_ids:
                item_name = (item.item or '').strip().lower()
                if not item_name:
                    continue

                product_line = gateway_config.gateway_config_line_ids.filtered(
                    lambda l: (l.name or '').strip().lower() == item_name
                )
                product = product_line[:1].product_id
                if not product or product.detailed_type != 'product' or not product.is_livestock:
                    continue

                if slaughter_obj.search_count([('api_donation_item_id', '=', item.id)]):
                    continue

                slaughter_vals = {
                    'product_id': product.id,
                    'donee_id': donation.donor_id.id,
                    'api_donation_item_id': item.id,
                    'quantity': int(item.qty or 1),
                    'price': item.total,
                    'ref': donation.name or donation.import_id,
                }
                slaughter_vals.update(donation._get_livestock_department_vals(product))

                try:
                    with self.env.cr.savepoint():
                        slaughter_obj.create(slaughter_vals)
                except IntegrityError:
                    continue


class APIDonationWizard(models.TransientModel):
    _inherit = 'api.donation.wizard'

    def _process_donations_bulk(self, donations_info, journal, gateway_config, company_currency, all_data, history):
        result = super()._process_donations_bulk(
            donations_info, journal, gateway_config, company_currency, all_data, history
        )
        if result.get('new_donations') and gateway_config:
            donations = self.env['api.donation'].browse(result['new_donations'])
            donations._create_livestock_slaughter_records(gateway_config)
        return result
