
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
        if 'chicken' in product_markers:
            return {'is_chicken_depart': True}
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

            for line in livestock_lines:
                vals = {
                    'product_id': line.product_id.id,
                    'donee_id': deposit.donor_id.id,
                    'ref': deposit.name,
                }
                vals.update(deposit._get_livestock_department_vals(line.product_id))
                # line.amount is the unit price
                slaughter_obj._create_for_source(
                    'direct_deposit_line_id', line, line.quantity, line.amount * line.quantity, vals)

    def action_clear(self):
        res = super().action_clear()
        self._create_livestock_slaughter_records()
        return res
