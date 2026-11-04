# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    amount_locked = fields.Boolean(
        compute='_compute_amount_locked',
        help='The bill of a Purchase Order is paid for what is still due on it: the amount cannot be changed.')

    # The amount of the wizard stays the tax-included one, so the bill is settled for all of it;
    # the payment is created for what is left after the tax (see account.payment).
    payment_tax_id = fields.Many2one(
        'account.tax', string='Tax', check_company=True, domain="[('type_tax_use', '=', 'purchase')]",
        help='Tax deducted from the tax-included amount.')
    payment_tax_amount = fields.Monetary(string='Tax Amount', compute='_compute_payment_tax_amount')
    payment_net_amount = fields.Monetary(string='Net Amount', compute='_compute_payment_tax_amount')

    @api.depends('line_ids')
    def _compute_amount_locked(self):
        for wizard in self:
            wizard.amount_locked = any(move._is_purchase_order_bill() for move in wizard.line_ids.move_id)

    @api.depends('payment_tax_id', 'amount', 'currency_id', 'partner_id')
    def _compute_payment_tax_amount(self):
        # Same figures as account.payment._get_payment_tax_values, on the amount of the wizard.
        for wizard in self:
            taxes = []
            if wizard.payment_tax_id and wizard.currency_id:
                taxes = wizard.payment_tax_id.compute_all(
                    wizard.amount, currency=wizard.currency_id, partner=wizard.partner_id)['taxes']
            wizard.payment_tax_amount = sum(abs(wizard.currency_id.round(tax['amount'])) for tax in taxes)
            wizard.payment_net_amount = wizard.amount - wizard.payment_tax_amount

    def _create_payment_vals_from_wizard(self, batch_result):
        vals = super()._create_payment_vals_from_wizard(batch_result)
        if self.payment_tax_id:
            vals.update({
                'payment_tax_id': self.payment_tax_id.id,
                'amount_tax_included': self.amount,
                'amount': self.payment_net_amount,
            })
        return vals

    def _create_payments(self):
        # The amount is read-only on the form; this keeps it from being set another way.
        self.ensure_one()
        if self.amount_locked and self.can_edit_wizard:
            amount_due = self._get_total_amount_in_wizard_currency_to_full_reconcile(self._get_batches()[0])[0]
            if self.currency_id.compare_amounts(self.amount, amount_due) != 0:
                raise UserError(_(
                    'The bill of a Purchase Order is paid for the amount still due on it. '
                    'The payment amount cannot be changed.'))
        if self.payment_tax_id and self.currency_id.compare_amounts(self.payment_net_amount, 0.0) <= 0:
            raise UserError(_('The tax %s takes the whole amount: nothing would be left to pay.', self.payment_tax_id.display_name))
        return super()._create_payments()
