from odoo import models, fields, api

class StockMove(models.Model):
    _inherit = 'stock.move'

    qty_available = fields.Float(
        string="On Hand",
        related='product_id.qty_available',
        digits='Product Unit of Measure',
        readonly=True,
        help="Quantity currently on hand for this product.",
    )
    
class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'
    
    qty_available = fields.Float(
        string="On Hand (Source)",
        compute='_compute_qty_available',
        digits='Product Unit of Measure',
    )

@api.depends('product_id', 'location_id')
def _compute_qty_available(self):
    for move in self:
        move.qty_available = (
            move.product_id.with_context(location=move.location_id.id).qty_available
            if move.product_id and move.location_id else 0.0
        )