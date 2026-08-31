from odoo import models, fields, api


class DailyPlanningLine(models.Model):
    _name = 'daily.planning.line'
    _description = 'Daily Planning Line'


    daily_planning_id = fields.Many2one('daily.planning', string='Daily Planning')

    product_id = fields.Many2one('product.product', string='Product')

    quantity = fields.Float(string='Quantity')
    
    on_hand_qty = fields.Float(
        string='On Hand Quantity',
        compute='_compute_on_hand_qty'
    )

    @api.depends('product_id')
    def _compute_on_hand_qty(self):
        source_loc = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        for rec in self:
            if rec.product_id and source_loc:
                rec.on_hand_qty = rec.product_id.with_context(
                    location=source_loc.id
                ).qty_available
            else:
                rec.on_hand_qty = 0.0