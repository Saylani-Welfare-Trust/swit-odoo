from odoo import models, fields, api


class StockMove(models.Model):
    _inherit = 'stock.move'

    on_hand_qty = fields.Float(
        string="On Hand Qty",
        compute="_compute_on_hand_qty",
        digits='Product Unit of Measure',
    )

    @api.depends('product_id', 'location_id', 'location_dest_id')
    def _compute_on_hand_qty(self):
        """On hand in the internal location of the move (source, else destination,
        sub-locations included); the total on hand when neither is internal."""
        for move in self:
            if not move.product_id:
                move.on_hand_qty = 0.0
                continue
            location = (move.location_id if move.location_id.usage == 'internal'
                        else move.location_dest_id if move.location_dest_id.usage == 'internal'
                        else False)
            product = move.product_id.with_context(location=location.id) if location else move.product_id
            move.on_hand_qty = product.qty_available