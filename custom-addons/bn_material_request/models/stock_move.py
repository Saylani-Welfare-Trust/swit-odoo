from odoo import models, fields, api

class StockMove(models.Model):
    _inherit = 'stock.move'

    on_hand_qty = fields.Float(
        string='On Hand',
        compute='_compute_on_hand_qty'
    )

    @api.depends('product_id', 'location_id')
    def _compute_on_hand_qty(self):
        for move in self:
            if move.product_id and move.location_id:
                move.on_hand_qty = move.product_id.with_context(
                    location=move.location_id.id
                ).qty_available
            else:
                move.on_hand_qty = 0.0