from odoo import _, api, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_create_purchase_request(self):
        """
        This method creates a Purchase Request and pre-fills the data
        from the Stock Picking and Stock Move lines, including the On Hand Quantity.
        """
        if self.state != 'done':
            raise UserError("You can create a purchase request only after validating the transfer.")

        purchase_request_vals = {
            'name': self.name,
            'origin': self.origin,
            'requested_by': self.env.user.id,
            'description': f"Generated from Picking {self.name}",
            'line_ids': [],
        }

        purchase_request_lines = []
        for move in self.move_ids_without_package:
            on_hand_qty = self.env['stock.quant'].search([
                ('product_id', '=', move.product_id.id),
                ('location_id', 'child_of', self.location_id.id),
            ]).quantity

            line_vals = (0, 0, {
                'product_id': move.product_id.id,
                'product_qty': move.quantity,
                'on_hand_qty': on_hand_qty,
                'description': move.name,
            })
            purchase_request_lines.append(line_vals)

        purchase_request_vals['line_ids'] = purchase_request_lines

        purchase_request = self.env['purchase.request'].create(purchase_request_vals)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Request',
            'res_model': 'purchase.request',
            'view_mode': 'form',
            'res_id': purchase_request.id,
            'target': 'current',
        }
