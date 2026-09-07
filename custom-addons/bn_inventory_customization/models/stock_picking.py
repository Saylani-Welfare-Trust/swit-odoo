from odoo import models, fields
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    bill_amount = fields.Float("Bill Amount")

    show_receive_by_weight = fields.Boolean(
        string="Show Receive by Weight Button",
        compute="_compute_show_receive_by_weight"
    )

    def _compute_show_receive_by_weight(self):
        for picking in self:
            picking.show_receive_by_weight = any(
                move.product_id.check_stock for move in picking.move_ids if move.product_id
            )

    def action_recieve_by_weight(self):
        """
        Deprecated method name - kept for backward compatibility.
        """
        return self.open_receive_by_weight_wizard()

    def open_receive_by_weight_wizard(self):
        """
        Open the receive-by-weight wizard for this picking.
        - If an existing unsent/unfinished wizard exists for this picking (is_received=False),
          open that one so saved data is preserved.
        - Otherwise create a new wizard and pre-populate lines from picking moves.
        """
        self.ensure_one()
        Wizard = self.env['receive.by.weight']

        # Try to find an existing (not yet completed) wizard for this picking
        existing = Wizard.search([('picking_id', '=', self.id), ('is_received', '=', False)], limit=1)
        if existing:
            # Found previously saved wizard — open it (preserves line_ids)
            return {
                'name': 'Receive by Weight',
                'type': 'ir.actions.act_window',
                'res_model': 'receive.by.weight',
                'view_mode': 'form',
                'target': 'new',
                'res_id': existing.id,
            }

        # No existing wizard — build initial lines and create a new one
        lines = []
        s_no = 1
        for move in self.move_ids:
            qty = int(move.product_uom_qty or 0)
            for _ in range(qty):
                lines.append((0, 0, {
                    's_no': s_no,
                    'product_id': move.product_id.id,
                    'quantity': 1.0,
                }))
                s_no += 1

        wizard = Wizard.create({
            'picking_id': self.id,
            'line_ids': lines,
        })

        return {
            'name': 'Receive by Weight',
            'type': 'ir.actions.act_window',
            'res_model': 'receive.by.weight',
            'view_mode': 'form',
            'target': 'new',
            'res_id': wizard.id,
        }