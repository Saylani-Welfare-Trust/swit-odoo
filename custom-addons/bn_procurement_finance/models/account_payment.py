# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import format_amount

FINANCE_GROUP = 'bn_procurement_finance.group_finance'

# Context key under which the Purchase Order itself writes on its advance payments.
SYSTEM_WRITE = 'po_advance_system_write'

# Only ever set by the Purchase Order.
PO_ADVANCE_LINK_FIELDS = (
    'purchase_order_id', 'po_payment_term_id', 'po_payment_term_line_id', 'po_milestone',
    'po_amount_total', 'po_advance_amount', 'po_review_required', 'po_review_reason',
)
# Come from the Purchase Order and stay as generated - the amount included: when it
# is out of date, the payment is cancelled and created again from the order.
PO_ADVANCE_LOCKED_FIELDS = (
    'partner_id', 'amount', 'currency_id', 'payment_type', 'partner_type', 'is_internal_transfer')


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    purchase_order_id = fields.Many2one(
        'purchase.order', string='Advance for Purchase Order', readonly=True, copy=False, index=True, ondelete='restrict',
        help='Purchase Order whose Payment Term generated this advance payment.')
    po_payment_term_id = fields.Many2one(
        'account.payment.term', string='PO Payment Term', readonly=True, copy=False)
    po_payment_term_line_id = fields.Many2one(
        'account.payment.term.line', string='PO Payment Term Line', readonly=True, copy=False, ondelete='set null')
    po_milestone = fields.Char(string='Payment Milestone', readonly=True, copy=False)
    # Figures as they were when the payment was generated, so a later change of the
    # Purchase Order or of the amount stays visible.
    po_amount_total = fields.Monetary(string='PO Amount', readonly=True, copy=False)
    po_advance_amount = fields.Monetary(
        string='Advance Amount', readonly=True, copy=False,
        help='Advance calculated from the Purchase Order total and its Payment Term.')

    po_review_required = fields.Boolean(string='Needs Finance Review', readonly=True, copy=False, tracking=True)
    po_review_reason = fields.Text(string='Review Reason', readonly=True, copy=False)

    # The amount entered is tax included: the tax is kept back on the account of the tax and
    # only the rest leaves the bank. That rest stays the amount of the payment.
    payment_tax_id = fields.Many2one(
        'account.tax', string='Tax', check_company=True, domain="[('type_tax_use', '=', 'purchase')]",
        help='Tax deducted from the tax-included amount.')
    amount_tax_included = fields.Monetary(string='Amount (Tax Included)')
    payment_tax_amount = fields.Monetary(string='Tax Amount', compute='_compute_payment_tax_amount', store=True)

    @api.depends('journal_id')
    def _compute_currency_id(self):
        # Picking another journal resets a payment to that journal's currency; an
        # advance payment stays in the currency of its Purchase Order.
        advances = self.filtered('purchase_order_id')
        for payment in advances:
            payment.currency_id = payment.currency_id
        super(AccountPayment, self - advances)._compute_currency_id()

    # ------------------------------------------------------------------
    # Tax deducted from the payment
    # ------------------------------------------------------------------
    @api.depends('payment_tax_id', 'amount_tax_included', 'currency_id')
    def _compute_payment_tax_amount(self):
        for payment in self:
            payment.payment_tax_amount = sum(abs(tax['amount']) for tax in payment._get_payment_tax_values())

    @api.onchange('payment_tax_id', 'amount_tax_included')
    def _onchange_payment_tax(self):
        if self.payment_tax_id:
            if not self.amount_tax_included:
                # The amount typed before the tax was chosen is the tax-included one.
                self.amount_tax_included = self.amount
            self.amount = self.amount_tax_included - self.payment_tax_amount
        elif self.amount_tax_included:
            # Tax removed: the whole amount is paid again.
            self.amount = self.amount_tax_included
            self.amount_tax_included = 0.0

    def _get_payment_tax_values(self):
        """The taxes of ``payment_tax_id`` on the tax-included amount, as ``compute_all`` gives them."""
        self.ensure_one()
        if not self.payment_tax_id or not self.currency_id:
            return []
        taxes = self.payment_tax_id.compute_all(
            self.amount_tax_included, currency=self.currency_id, partner=self.partner_id)['taxes']
        for tax in taxes:
            tax['amount'] = self.currency_id.round(tax['amount'])
        return [tax for tax in taxes if not self.currency_id.is_zero(tax['amount'])]

    def _prepare_payment_tax_line_vals(self):
        """Journal items of the deducted tax, on the side of the bank line: the vendor is
        debited with the tax-included amount, the bank and the tax are credited."""
        self.ensure_one()
        sign = -1 if self.payment_type == 'outbound' else 1
        line_vals = []
        for tax in self._get_payment_tax_values():
            account = self.env['account.tax.repartition.line'].browse(tax['tax_repartition_line_id']).account_id
            if not account:
                raise UserError(_('Set an account on the tax %s before using it on a payment.', tax['name']))
            if account.account_type in ('asset_receivable', 'liability_payable'):
                raise UserError(_(
                    'The account %(account)s of the tax %(tax)s is a receivable/payable account and cannot '
                    'take the tax deducted on a payment.', account=account.display_name, tax=tax['name']))
            amount_currency = sign * abs(tax['amount'])
            line_vals.append({
                'name': tax['name'],
                'account_id': account.id,
                'partner_id': self.partner_id.id,
                'currency_id': self.currency_id.id,
                'amount_currency': amount_currency,
                'balance': self.currency_id._convert(
                    amount_currency, self.company_id.currency_id, self.company_id, self.date),
                'is_payment_tax_line': True,
            })
        return line_vals

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        self.ensure_one()
        tax_lines = self.move_id.line_ids.filtered('is_payment_tax_line')
        if tax_lines and write_off_line_vals:
            # Entry synced again: its tax lines came in as the write-off. Only a real
            # write-off is kept, the tax lines are built again from the tax below.
            other_lines = self._seek_for_lines()[2] - tax_lines
            write_off_line_vals = [{
                'name': other_lines[0].name,
                'account_id': other_lines[0].account_id.id,
                'partner_id': other_lines[0].partner_id.id,
                'currency_id': other_lines[0].currency_id.id,
                'amount_currency': sum(other_lines.mapped('amount_currency')),
                'balance': sum(other_lines.mapped('balance')),
            }] if other_lines else []
        if self.payment_tax_id:
            write_off_line_vals = list(write_off_line_vals or []) + self._prepare_payment_tax_line_vals()
        return super()._prepare_move_line_default_vals(
            write_off_line_vals=write_off_line_vals, force_balance=force_balance)

    @api.model
    def _get_trigger_fields_to_synchronize(self):
        return super()._get_trigger_fields_to_synchronize() + ('payment_tax_id', 'amount_tax_included')

    # ------------------------------------------------------------------
    # Payment controls
    # ------------------------------------------------------------------
    def _get_po_advance_changes(self, vals):
        """The controlled fields that ``vals`` would really change on this payment.
        Syncing from the journal entry writes these fields back with the values
        they already have, which is not a change."""
        self.ensure_one()
        changed = []
        for name in PO_ADVANCE_LINK_FIELDS + PO_ADVANCE_LOCKED_FIELDS:
            if name not in vals:
                continue
            field, old, new = self._fields[name], self[name], vals[name]
            if field.type == 'many2one':
                differs = old.id != (new or False)
            elif field.type == 'monetary':
                differs = self.currency_id.compare_amounts(old, new or 0.0) != 0
            else:
                differs = (old or False) != (new or False)
            if differs:
                changed.append(name)
        return changed

    def write(self, vals):
        if self.env.context.get(SYSTEM_WRITE):
            return super().write(vals)
        for payment in self:
            changed = payment._get_po_advance_changes(vals)
            if not changed:
                continue
            if set(changed).intersection(PO_ADVANCE_LINK_FIELDS):
                raise UserError(_('The link between a payment and its Purchase Order is set by the system and cannot be changed.'))
            if not payment.purchase_order_id:
                continue
            locked = [
                payment._fields[name] for name in changed
                if name in PO_ADVANCE_LOCKED_FIELDS
                and not (name == 'amount' and payment.move_id.state != 'posted')
            ]
            if locked:
                raise UserError(_(
                    'This advance payment was generated from Purchase Order %(order)s: '
                    'its %(fields)s cannot be changed.',
                    order=payment.purchase_order_id.display_name,
                    fields=', '.join(field._description_string(self.env) for field in locked)))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_po_advance(self):
        for payment in self:
            if payment.purchase_order_id and payment.state != 'cancel':
                raise UserError(_(
                    'This is the advance payment of Purchase Order %s and cannot be deleted. Cancel it instead.',
                    payment.purchase_order_id.display_name))

    def action_po_advance_reviewed(self):
        """Finance has looked at a flagged advance payment and decided what to do with it."""
        if not self.env.user.has_group(FINANCE_GROUP):
            raise UserError(_('Only Finance users can mark an advance payment as reviewed.'))
        for payment in self.filtered('po_review_required'):
            payment.with_context(**{SYSTEM_WRITE: True}).write({
                'po_review_required': False,
                'po_review_reason': False,
            })
            payment.message_post(body=_('Review completed by %s.', self.env.user.display_name))
        return True

    # ------------------------------------------------------------------
    # Deducting the advance from the vendor bill
    # ------------------------------------------------------------------
    def action_post(self):
        res = super().action_post()
        self.filtered('purchase_order_id')._reconcile_po_advance()
        return res

    def _reconcile_po_advance(self, bills=None):
        """Deduct posted advance payments from the vendor bills of their Purchase
        Order, so only the remainder is still due on the bill. Limited to ``bills``
        when given, otherwise every posted bill of the order is considered."""
        for payment in self.sudo():
            order = payment.purchase_order_id
            if not order or payment.state != 'posted':
                continue
            order_bills = order.invoice_ids if bills is None else bills.sudo().filtered(
                lambda bill: order in bill.line_ids.purchase_line_id.order_id)
            order_bills = order_bills.filtered(lambda bill: (
                bill.state == 'posted' and bill.move_type == 'in_invoice'
                and bill.commercial_partner_id == payment.partner_id.commercial_partner_id))
            advance_lines = payment._seek_for_lines()[1].filtered(lambda line: not line.reconciled and line.balance > 0)
            bill_lines = order_bills.line_ids.filtered(lambda line: (
                line.account_id.account_type == 'liability_payable' and not line.reconciled and line.balance < 0
                and line.account_id in advance_lines.account_id))
            if not advance_lines or not bill_lines:
                continue
            residual_before = {bill: bill.amount_residual for bill in bill_lines.move_id}
            (advance_lines + bill_lines).reconcile()
            for bill, before in residual_before.items():
                deducted = before - bill.amount_residual
                if bill.currency_id.is_zero(deducted):
                    continue
                bill.message_post(body=_(
                    'Advance payment %(payment)s of %(order)s deducted: %(amount)s. Remaining payable: %(residual)s.',
                    payment=payment._get_html_link(), order=order._get_html_link(),
                    amount=format_amount(self.env, deducted, bill.currency_id),
                    residual=format_amount(self.env, bill.amount_residual, bill.currency_id)))


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    is_payment_tax_line = fields.Boolean(readonly=True, help='Tax deducted on a payment.')
