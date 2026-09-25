from odoo import models, fields, api


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    on_hand_qty = fields.Float(
        string="On Hand Qty",
        compute="_compute_on_hand_qty",
        digits='Product Unit of Measure',
    )

    @api.depends('product_id', 'location_id', 'lot_id')
    def _compute_on_hand_qty(self):
        for line in self:
            if not line.product_id or not line.location_id:
                line.on_hand_qty = 0.0
                continue

            domain = [
                ('product_id', '=', line.product_id.id),
                ('location_id', '=', line.location_id.id),
            ]
            if line.lot_id:
                domain.append(('lot_id', '=', line.lot_id.id))

            quants = self.env['stock.quant'].search(domain)
            line.on_hand_qty = sum(quants.mapped('quantity'))