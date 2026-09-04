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
        
    def button_validate(self):
        """Standard validation, then auto-create the vendor bill for
        incoming receipts that are linked to a purchase order.

        NOTE: button_validate() can return an action dict instead of True
        when Odoo needs to show an intermediate wizard (backorder
        confirmation, immediate transfer confirmation, etc). In that case
        the picking is NOT yet in state 'done', so we simply skip bill
        creation here - checking picking.state == 'done' below already
        guards against that automatically.
        """
        res = super().button_validate()

        for picking in self:
            if (
                picking.state == 'done'
                and picking.picking_type_id.code == 'incoming'
                and picking.purchase_id
            ):
                picking._roq_create_vendor_bill_from_purchase()

        return res

    def _roq_create_vendor_bill_from_purchase(self):
        """Create the vendor bill for this receipt's purchase order,
        reusing the standard purchase.order.action_create_invoice() flow.
        """
        self.ensure_one()
        purchase = self.purchase_id

        if not purchase or purchase.state not in ('purchase', 'done'):
            return

        # Nothing left to bill (e.g. fully invoiced already, or invoicing
        # policy is "ordered quantity" and it was already billed at
        # confirmation) - nothing to do.
        if purchase.invoice_status != 'to invoice':
            return

        try:
            purchase.action_create_invoice()
        except UserError:
            # Don't block/undo the receipt validation if a bill can't be
            # generated (e.g. missing vendor bill reference requirements).
            # The user can still create it manually from the PO afterwards.
            pass

