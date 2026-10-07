# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    amount_locked = fields.Boolean(
        compute='_compute_amount_locked',
        help='The bill of a Purchase Order is paid for what is still due on it: the amount cannot be changed.')

    @api.depends('line_ids')
    def _compute_amount_locked(self):
        for wizard in self:
            wizard.amount_locked = any(move._is_purchase_order_bill() for move in wizard.line_ids.move_id)

    def _create_payments(self):
        # The amount is read-only on the form; this keeps it from being set another way.
        self.ensure_one()
        if self.amount_locked and self.can_edit_wizard:
            amount_due = self._get_total_amount_in_wizard_currency_to_full_reconcile(self._get_batches()[0])[0]
            if self.currency_id.compare_amounts(self.amount, amount_due) != 0:
                raise UserError(_(
                    'The bill of a Purchase Order is paid for the amount still due on it. '
                    'The payment amount cannot be changed.'))
        return super()._create_payments()
