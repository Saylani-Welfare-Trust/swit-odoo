from odoo import fields, models, _
from odoo.exceptions import UserError


class ReceiptReasonWizard(models.TransientModel):
    _name = 'receipt.reason.wizard'
    _description = 'Receipt Reason'

    picking_ids = fields.Many2many('stock.picking', 'receipt_reason_wizard_picking_rel',
                                   string='Receipts', readonly=True)
    reason_type = fields.Selection([
        ('no_backorder', 'No Backorder'),
        ('cancel', 'Receipt Cancelled'),
    ], required=True, readonly=True)
    # Required in the view only: the wizard is created before the reason is typed in.
    reason = fields.Text(string='Reason')
    # No Backorder: the backorder question this wizard interrupted, and the
    # receipts it was validating, to carry on with once the reason is given.
    backorder_confirmation_id = fields.Many2one('stock.backorder.confirmation', readonly=True)
    validate_picking_ids = fields.Many2many('stock.picking', 'receipt_reason_wizard_validate_picking_rel',
                                            readonly=True)

    def action_confirm(self):
        self.ensure_one()
        if not (self.reason or '').strip():
            raise UserError(_('Please enter the reason.'))
        label = dict(self._fields['reason_type'].selection)[self.reason_type]
        for picking in self.picking_ids:
            # sudo: whoever validates or cancels the receipt need not be able
            # to edit its Purchase Order.
            for order in picking.move_ids.purchase_line_id.order_id.sudo():
                self.env['purchase.receipt.reason'].sudo().create({
                    'order_id': order.id,
                    'picking_id': picking.id,
                    'reason_type': self.reason_type,
                    'reason': self.reason,
                })
                order.message_post(body=_(
                    '%(action)s on receipt %(receipt)s. Reason: %(reason)s',
                    action=label, receipt=picking.name, reason=self.reason))

        if self.reason_type == 'cancel':
            self.picking_ids.action_cancel()
            return True
        return self.backorder_confirmation_id.with_context(
            button_validate_picking_ids=self.validate_picking_ids.ids,
            receipt_reason_given=True,
        ).process_cancel_backorder()
