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

            quants = self.env['stock.quant'].search([
                ('product_id', '=', move.product_id.id),
                ('location_id', '=', move.location_id.id),
            ])
            move.on_hand_qty = sum(quants.mapped('quantity'))