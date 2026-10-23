from psycopg2 import IntegrityError

from odoo import models


class DirectDeposit(models.Model):
    _inherit = 'direct.deposit'

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
        """Mirrors pos.order._create_livestock_slaughter_records() - a Direct
        Deposit is only cleared once the bank transfer is confirmed, so its
        is_livestock lines fall into livestock at that point, same as a
        cleared cheque."""
        slaughter_obj = self.env['livestock.slaugther'].sudo()

        for deposit in self:
            livestock_lines = deposit.direct_deposit_line_ids.filtered(
                lambda line: line.product_id.is_livestock and line.quantity > 0
            )
            if not livestock_lines:
                continue

            existing_line_ids = set(slaughter_obj.search([
                ('direct_deposit_line_id', 'in', livestock_lines.ids),
            ]).mapped('direct_deposit_line_id').ids)

            for line in livestock_lines:
                if line.id in existing_line_ids:
                    continue

                slaughter_vals = {
                    'product_id': line.product_id.id,
                    'donee_id': deposit.donor_id.id,
                    'direct_deposit_line_id': line.id,
                    'quantity': int(line.quantity),
                    'price': line.amount,
                    'ref': deposit.name,
                }
                slaughter_vals.update(deposit._get_livestock_department_vals(line.product_id))

                try:
                    with self.env.cr.savepoint():
                        slaughter_obj.create(slaughter_vals)
                except IntegrityError:
                    continue

    def action_clear(self):
        res = super().action_clear()
        self._create_livestock_slaughter_records()
        return res
