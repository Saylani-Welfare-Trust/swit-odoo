from odoo import models, fields, api

class StockMove(models.Model):
    _inherit = 'stock.move'

    on_hand_qty = fields.Float(
        string="On Hand Qty",
        compute="_compute_on_hand_qty",
        digits='Product Unit of Measure',
    )

    @api.depends('product_id')
    def _compute_on_hand_qty(self):
        for move in self:
            move.on_hand_qty = move.product_id.qty_available if move.product_id else 0.0