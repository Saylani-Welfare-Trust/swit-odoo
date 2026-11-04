from odoo import models


class StockBackorderConfirmation(models.TransientModel):
    _inherit = 'stock.backorder.confirmation'

    def process_cancel_backorder(self):
        """No Backorder on a Purchase Order's receipt first asks for the reason,
        which is kept on that Purchase Order."""
        receipts = self.pick_ids.filtered(
            lambda picking: picking.picking_type_code == 'incoming' and picking.purchase_id)
        if receipts and not self.env.context.get('receipt_reason_given'):
            validate_pickings = self.env['stock.picking'].browse(
                self.env.context.get('button_validate_picking_ids') or [])
            return receipts._open_receipt_reason_wizard(
                'no_backorder', backorder_confirmation=self, validate_pickings=validate_pickings)
        return super().process_cancel_backorder()
