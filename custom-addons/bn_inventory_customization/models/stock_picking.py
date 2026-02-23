from odoo import models
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'


    def action_recieve_by_weight(self):
        self.ensure_one()
        
        lines = []

        # Filter only moves with products marked as receive by weight
        moves = self.move_ids.filtered(lambda m: m.product_id.is_receive_by_weight and m.product_id.is_livestock)

        if not moves:
            raise ValidationError('Sorry you cannot receive this product.')

        for move in moves:
            qty = int(move.product_uom_qty or 0)

            for _ in range(qty):
                lines.append((0, 0, {
                    'product_id': move.product_id.id,
                    'quantity': 1.0,
                }))

        wizard = self.env['receive.by.weight'].create({
            'picking_id': self.id,
            'line_ids': lines,
        })

        return {
            'name': 'Receive by Weight',
            'type': 'ir.actions.act_window',
            'res_model': 'receive.by.weight',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }