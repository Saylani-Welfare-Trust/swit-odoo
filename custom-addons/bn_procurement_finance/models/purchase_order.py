# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import format_amount
from odoo.tools.misc import clean_context

from .account_payment import SYSTEM_WRITE

# Changing any of these on a confirmed order can make its advance payment out of date.
ADVANCE_WATCHED_FIELDS = {'order_line', 'payment_term_id', 'partner_id', 'currency_id'}


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    advance_payment_ids = fields.One2many(
        'account.payment', 'purchase_order_id', string='Advance Payments', readonly=True, copy=False)
    advance_payment_count = fields.Integer(compute='_compute_advance_payment_info')
    advance_review_required = fields.Boolean(compute='_compute_advance_payment_info')
    advance_review_reason = fields.Text(compute='_compute_advance_payment_info')
    advance_payment_missing = fields.Boolean(
        compute='_compute_advance_payment_info',
        help='The Payment Term has an advance milestone for which no payment exists yet.')

    @api.depends('advance_payment_ids.state', 'advance_payment_ids.po_review_required',
                 'advance_payment_ids.po_review_reason', 'payment_term_id', 'amount_total', 'state')
    def _compute_advance_payment_info(self):
        for order in self:
            # sudo: purchase users see the figures without needing accounting rights.
            payments = order.sudo().advance_payment_ids
            live = payments.filtered(lambda p: p.state != 'cancel')
            flagged = live.filtered('po_review_required')
            order.advance_payment_count = len(payments)
            order.advance_review_required = bool(flagged)
            order.advance_review_reason = '\n'.join(dict.fromkeys(flagged.mapped('po_review_reason'))) or False
            order.advance_payment_missing = order.state in ('purchase', 'done') and any(
                amount > 0 and line not in live.po_payment_term_line_id
                for line, _label, amount in order._get_advance_milestones())

    # ------------------------------------------------------------------
    # Advance payment generation
    # ------------------------------------------------------------------
    def _get_advance_milestones(self):
        """[(payment term line, milestone label, amount)] for every "Advance
        Payment" line of the order's Payment Term. A percentage is taken on the
        order total, taxes included - the basis the vendor bill is split on too."""
        self.ensure_one()
        milestones = []
        for line in self.payment_term_id.line_ids.filtered(lambda l: l.milestone_type == 'advance'):
            if line.value == 'percent':
                amount = self.currency_id.round(self.amount_total * line.value_amount / 100.0)
                label = _('Advance Payment (%s%%)', '%g' % line.value_amount)
            else:
                amount = self.currency_id.round(min(line.value_amount, self.amount_total))
                label = _('Advance Payment (fixed amount)')
            milestones.append((line, label, amount))
        return milestones

    def _get_live_advance_payments(self):
        self.ensure_one()
        return self.sudo().advance_payment_ids.filtered(lambda p: p.state != 'cancel')

    def _get_advance_journal(self):
        """Journal the draft is prepared on: a bank journal in the order's currency
        where there is one. Finance picks the actual one before posting."""
        self.ensure_one()
        journals = self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(self.company_id),
            ('type', 'in', ('bank', 'cash')),
            ('outbound_payment_method_line_ids', '!=', False),
        ])
        company_currency = self.company_id.currency_id
        return journals.sorted(lambda j: (j.type != 'bank', (j.currency_id or company_currency) != self.currency_id))[:1]

    def _create_advance_payments(self, raise_errors=False):
        """Create the draft vendor payment of every advance milestone that has none
        yet. Unless ``raise_errors``, a failure is reported on the order instead of
        undoing the confirmation that triggered it - Create Advance Payment then
        stays available to do it by hand."""
        payments = self.env['account.payment']
        for order in self.filtered(lambda o: o.state in ('purchase', 'done')):
            try:
                with self.env.cr.savepoint():
                    payments |= order._create_order_advance_payments(raise_errors=raise_errors)
            except UserError as e:
                if raise_errors:
                    raise
                order.message_post(body=_('The advance payment could not be created automatically: %s', e))
        return payments

    def _create_order_advance_payments(self, raise_errors=False):
        self.ensure_one()
        # sudo: the user confirming the order usually has no right to create payments.
        order = self.sudo().with_company(self.company_id)
        payments = order.env['account.payment']
        milestones = [milestone for milestone in order._get_advance_milestones() if milestone[2] > 0]
        if not milestones:
            return payments
        # Two confirmations at the same time must not both find "no payment yet".
        self.env.cr.execute('SELECT id FROM purchase_order WHERE id = %s FOR UPDATE', [order.id])
        live = order._get_live_advance_payments()
        advance_lines = self.env['account.payment.term.line'].union(*(line for line, _label, _amount in milestones))
        outdated = live.filtered(lambda p: p.po_payment_term_line_id not in advance_lines)
        if outdated:
            # A second advance on top of one from the previous Payment Term would pay the vendor twice.
            reason = _(
                'The Payment Term of %(order)s is now "%(term)s", which this advance payment was not '
                'generated from. No new advance payment is created until this one is cancelled.',
                order=order.name, term=order.payment_term_id.display_name)
            if raise_errors:
                raise UserError(reason)
            order._flag_advance_payments_for_review(reason, payments=outdated)
            return payments
        journal = order._get_advance_journal()
        for line, label, amount in milestones:
            if line in live.po_payment_term_line_id:
                continue
            if not journal:
                raise UserError(_(
                    'No bank or cash journal with an outgoing payment method is set up for %s.',
                    order.company_id.display_name))
            payment = payments.with_context({**clean_context(order.env.context), SYSTEM_WRITE: True}).create({
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                # The commercial partner carries the payable, on the vendor bill as well.
                'partner_id': order.partner_id.commercial_partner_id.id,
                'amount': amount,
                'currency_id': order.currency_id.id,
                'journal_id': journal.id,
                'date': fields.Date.context_today(order),
                'ref': _('Advance - %(order)s - %(milestone)s', order=order.name, milestone=label),
                'purchase_order_id': order.id,
                'po_payment_term_id': order.payment_term_id.id,
                'po_payment_term_line_id': line.id,
                'po_milestone': label,
                'po_amount_total': order.amount_total,
                'po_advance_amount': amount,
            })
            payment.message_post(body=_(
                'Generated from Purchase Order %(order)s: %(milestone)s of %(total)s under Payment Term "%(term)s".',
                order=order._get_html_link(), milestone=label,
                total=format_amount(self.env, order.amount_total, order.currency_id),
                term=order.payment_term_id.display_name))
            order.message_post(body=_(
                'Draft %(payment)s created for Finance: %(milestone)s = %(amount)s.',
                payment=payment._get_html_link(title=_('advance payment')), milestone=label,
                amount=format_amount(self.env, amount, order.currency_id)))
            payments |= payment
        return payments

    def button_approve(self, force=False):
        pending = self.filtered(lambda o: o.state not in ('purchase', 'done'))
        res = super().button_approve(force=force)
        pending._create_advance_payments()
        return res

    def action_create_advance_payments(self):
        """For orders confirmed before their Payment Term had an advance milestone,
        or once Finance has dealt with an advance payment that was under review."""
        if not self.env.user.has_group('account.group_account_invoice'):
            raise UserError(_('Only accounting users can create an advance payment.'))
        if not self._create_advance_payments(raise_errors=True):
            raise UserError(_('There is no advance payment left to create for this Purchase Order.'))
        return self.action_view_advance_payments()

    def action_view_advance_payments(self):
        self.ensure_one()
        payments = self.sudo().advance_payment_ids
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_account_payments_payable')
        action['domain'] = [('purchase_order_id', '=', self.id)]
        action['context'] = {'create': False}
        if len(payments) == 1:
            action.update({'views': [(False, 'form')], 'res_id': payments.id})
        return action

    # ------------------------------------------------------------------
    # Amendment / cancellation
    # ------------------------------------------------------------------
    def _get_advance_snapshot(self):
        self.ensure_one()
        return {
            'amount_total': self.amount_total,
            'payment_term_id': self.payment_term_id,
            'partner_id': self.partner_id,
            'currency_id': self.currency_id,
        }

    def _get_advance_changes(self, before):
        """What changed on the order since the ``before`` snapshot, in words."""
        self.ensure_one()
        changes = []
        if before['currency_id'].compare_amounts(before['amount_total'], self.amount_total) != 0:
            changes.append(_(
                'order total changed from %(old)s to %(new)s',
                old=format_amount(self.env, before['amount_total'], before['currency_id']),
                new=format_amount(self.env, self.amount_total, self.currency_id)))
        for name in ('payment_term_id', 'partner_id', 'currency_id'):
            if before[name] != self[name]:
                changes.append(_(
                    '%(field)s changed from "%(old)s" to "%(new)s"',
                    field=self._fields[name]._description_string(self.env),
                    old=before[name].display_name or _('none'), new=self[name].display_name or _('none')))
        return changes

    def _flag_advance_payments_for_review(self, reason, payments=None):
        """Put the order's advance payments under Finance review. They are never
        changed, cancelled or deleted here: what to do with them is Finance's call."""
        self.ensure_one()
        payments = self._get_live_advance_payments() if payments is None else payments.sudo()
        if not payments:
            return
        milestones = {line: amount for line, _label, amount in self._get_advance_milestones()}
        for payment in payments:
            details = reason
            expected = milestones.get(payment.po_payment_term_line_id)
            if self.state != 'cancel' and expected is not None \
                    and payment.currency_id.compare_amounts(expected, payment.amount) != 0:
                details = _(
                    '%(reason)s The advance for this milestone would now be %(expected)s; the payment is %(amount)s.',
                    reason=reason,
                    expected=format_amount(self.env, expected, self.currency_id),
                    amount=format_amount(self.env, payment.amount, payment.currency_id))
            pending = payment.po_review_reason if payment.po_review_required else False
            payment.with_context(**{SYSTEM_WRITE: True}).write({
                'po_review_required': True,
                'po_review_reason': '\n'.join(dict.fromkeys(filter(None, [pending, details]))),
            })
            payment.message_post(body=_('Finance review required: %s', details))
        self.message_post(body=_('Advance payment flagged for Finance review: %s', reason))

    def write(self, vals):
        if not ADVANCE_WATCHED_FIELDS.intersection(vals):
            return super().write(vals)
        snapshots = {
            order: order._get_advance_snapshot()
            for order in self
            if order.state in ('purchase', 'done') and order._get_live_advance_payments()
        }
        res = super().write(vals)
        for order, before in snapshots.items():
            changes = order._get_advance_changes(before)
            if changes:
                order._flag_advance_payments_for_review(_(
                    'Purchase Order %(order)s was amended after this advance payment was generated: %(changes)s.',
                    order=order.name, changes='; '.join(changes)))
        return res

    def button_cancel(self):
        res = super().button_cancel()
        for order in self:
            payments = order._get_live_advance_payments()
            draft = payments.filtered(lambda p: p.state == 'draft')
            if draft:
                order._flag_advance_payments_for_review(_(
                    'Purchase Order %s was cancelled. This draft advance payment was left as it is: '
                    'cancel it if it is no longer needed.', order.name), payments=draft)
            if payments - draft:
                order._flag_advance_payments_for_review(_(
                    'Purchase Order %s was cancelled after this advance was paid. Any refund or reversal '
                    'has to follow the Finance process.', order.name), payments=payments - draft)
        return res
