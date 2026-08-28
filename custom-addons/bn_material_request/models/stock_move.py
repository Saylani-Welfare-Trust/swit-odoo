from odoo import models, fields, api

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    on_hand_qty = fields.Float(
        string='On Hand',
        compute='_compute_on_hand_qty'
    )

    @api.depends('product_id', 'location_id')
    def _compute_on_hand_qty(self):
        for line in self:
            if line.product_id and line.location_id:
                line.on_hand_qty = line.product_id.with_context(
                    location=line.location_id.id
                ).qty_available
            else:
                line.on_hand_qty = 0.0