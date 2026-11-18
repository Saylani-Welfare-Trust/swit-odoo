from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # Outstanding microfinance balance after an installment paid in POS, shown on the receipt
    has_microfinance_remaining = fields.Boolean(copy=False)
    microfinance_remaining_amount = fields.Float(string='Microfinance Remaining Amount', copy=False)

    @api.model
    def _order_fields(self, ui_order):
        vals = super()._order_fields(ui_order)
        microfinance_data = (ui_order.get('extra_data') or {}).get('microfinance') or {}
        if microfinance_data.get('remaining_amount') is not None:
            vals['has_microfinance_remaining'] = True
            vals['microfinance_remaining_amount'] = microfinance_data['remaining_amount']
        return vals
