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


    payment_tax_id = fields.Many2one(
        'account.tax', string='Tax', check_company=True,
        domain="[('type_tax_use', '=', 'purchase')]",
        help='Tax deducted from the tax-included amount.'
    )
    amount_tax_included = fields.Monetary(string='Amount (Tax Included)')
    payment_tax_amount = fields.Monetary(
        string='Tax Amount', compute='_compute_payment_tax_amount', store=True
    )

    @api.depends('payment_tax_id', 'amount_tax_included', 'currency_id')
    def _compute_payment_tax_amount(self):
        for wizard in self:
            if not wizard.payment_tax_id or not wizard.currency_id:
                wizard.payment_tax_amount = 0.0
                continue
            
            taxes = wizard.payment_tax_id.compute_all(
                wizard.amount_tax_included, 
                currency=wizard.currency_id, 
                partner=wizard.partner_id
            )['taxes']
            
            amount = 0.0
            for tax in taxes:
                amount += wizard.currency_id.round(tax['amount'])
            wizard.payment_tax_amount = amount

    @api.onchange('payment_tax_id', 'amount_tax_included')
    def _onchange_payment_tax(self):
        """Automatically adjust the 'Amount' field when tax fields change."""
        if self.payment_tax_id:
            if not self.amount_tax_included:
                # If the user typed the amount before choosing the tax, assume it's tax-included
                self.amount_tax_included = self.amount
            
            # The actual amount to pay is the tax-included amount minus the tax
            self.amount = self.amount_tax_included - self.payment_tax_amount
        
        elif self.amount_tax_included:
            # Tax removed: the whole amount is paid again.
            self.amount = self.amount_tax_included
            self.amount_tax_included = 0.0

    def _create_payment_vals_from_wizard(self, batch_result):
        """Pass the custom tax fields to the created account.payment."""
        vals = super()._create_payment_vals_from_wizard(batch_result)
        
        vals.update({
            'payment_tax_id': self.payment_tax_id.id,
            'amount_tax_included': self.amount_tax_included,
        })
        return vals