from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    # set by Receive by Weight on the moves of the weighed units
    livestock_weight = fields.Float('Weighed (kg)', digits='Stock Weight', readonly=True, copy=False)
    livestock_amount = fields.Monetary(
        'Weighed Amount', currency_field='livestock_currency_id', readonly=True, copy=False,
        help="Weight x the per-kg price of the purchase line, in the purchase order's currency.")
    livestock_currency_id = fields.Many2one(related='purchase_line_id.currency_id')

    def _livestock_price_per_kg(self):
        """The purchase line's price per kg (its price is per kg x the heaviest band)."""
        self.ensure_one()
        line = self.purchase_line_id
        if not line:
            return 0.0
        return line.x_base_price or (line.price_unit / (line.to_kg_multiplier or 1.0))

    def _get_price_unit(self):
        """A weighed unit is valued at its weighed amount, not at the purchase
        line's estimated price (per kg x heaviest band)."""
        self.ensure_one()
        if self.livestock_amount and self.product_uom_qty and self.purchase_line_id \
                and not self.origin_returned_move_id:
            order = self.purchase_line_id.order_id
            price_unit = self.livestock_amount / self.product_uom_qty
            if order.currency_id != order.company_id.currency_id:
                price_unit = order.currency_id._convert(
                    price_unit, order.company_id.currency_id, order.company_id,
                    fields.Date.context_today(self), round=False)
            return price_unit
        return super()._get_price_unit()
