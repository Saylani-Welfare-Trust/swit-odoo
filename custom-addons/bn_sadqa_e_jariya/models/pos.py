from odoo import models, api


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _order_fields(self, ui_order):
        vals = super()._order_fields(ui_order)
        if (ui_order.get('extra_data') or {}).get('sadqa_jariya'):
            vals['is_non_donation_receipt'] = True
        return vals
