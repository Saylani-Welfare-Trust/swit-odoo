from odoo import models, fields, api

class StockMove(models.Model):
    _inherit = 'stock.move'

    on_hand_qty = fields.Float(
        string="On Hand Qty",
        compute="_compute_on_hand_qty",
        digits='Product Unit of Measure',
    )

    @api.depends('product_id', 'location_id')
    def _compute_on_hand_qty(self):
        for move in self:
            if not move.product_id or not move.location_id:
                move.on_hand_qty = 0.0
                continue

            # Odoo's built-in method handles child locations automatically
            move.on_hand_qty = move.product_id.with_context(
                location=move.location_id.id,
                company_owned=True
            ).qty_available