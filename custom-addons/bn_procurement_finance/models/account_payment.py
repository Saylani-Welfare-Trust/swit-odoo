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
# Come from the Purchase Order and stay as generated.
PO_ADVANCE_LOCKED_FIELDS = ('partner_id', 'currency_id', 'payment_type', 'partner_type', 'is_internal_transfer')


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
    po_advance_amount_locked = fields.Boolean(
        compute='_compute_po_advance_amount_locked',
        help='Whether the current user may not change the amount: only Finance users can, on an advance payment.')

    @api.depends_context('uid')
    @api.depends('purchase_order_id')
    def _compute_po_advance_amount_locked(self):
        is_finance = self.env.user.has_group(FINANCE_GROUP)
        for payment in self:
            payment.po_advance_amount_locked = bool(payment.purchase_order_id) and not is_finance

    @api.depends('journal_id')
    def _compute_currency_id(self):
        # Picking another journal resets a payment to that journal's currency; an
        # advance payment stays in the currency of its Purchase Order.
        advances = self.filtered('purchase_order_id')
        for payment in advances:
            payment.currency_id = payment.currency_id
        super(AccountPayment, self - advances)._compute_currency_id()

    # ------------------------------------------------------------------
    # Payment controls
    # ------------------------------------------------------------------
    def _get_po_advance_changes(self, vals):
        """The controlled fields that ``vals`` would really change on this payment.
        Syncing from the journal entry writes these fields back with the values
        they already have, which is not a change."""
        self.ensure_one()
        changed = []
        for name in PO_ADVANCE_LINK_FIELDS + PO_ADVANCE_LOCKED_FIELDS + ('amount',):
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
        previous_amounts = {}
        for payment in self:
            changed = payment._get_po_advance_changes(vals)
            if not changed:
                continue
            if set(changed).intersection(PO_ADVANCE_LINK_FIELDS):
                raise UserError(_('The link between a payment and its Purchase Order is set by the system and cannot be changed.'))
            if not payment.purchase_order_id:
                continue
            locked = [payment._fields[name] for name in changed if name in PO_ADVANCE_LOCKED_FIELDS]
            if locked:
                raise UserError(_(
                    'This advance payment was generated from Purchase Order %(order)s: '
                    'its %(fields)s cannot be changed.',
                    order=payment.purchase_order_id.display_name,
                    fields=', '.join(field._description_string(self.env) for field in locked)))
            if 'amount' in changed:
                if not self.env.user.has_group(FINANCE_GROUP):
                    raise UserError(_(
                        'The amount of this advance payment is calculated from Purchase Order %s. '
                        'Only Finance users can change it.', payment.purchase_order_id.display_name))
                previous_amounts[payment] = payment.amount
        res = super().write(vals)
        for payment, previous in previous_amounts.items():
            payment.message_post(body=_(
                'Advance amount changed from %(old)s to %(new)s by %(user)s '
                '(calculated from the Purchase Order: %(calculated)s).',
                old=format_amount(self.env, previous, payment.currency_id),
                new=format_amount(self.env, payment.amount, payment.currency_id),
                user=self.env.user.display_name,
                calculated=format_amount(self.env, payment.po_advance_amount, payment.currency_id)))
        return res

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
