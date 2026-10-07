# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import format_amount


class AccountMove(models.Model):
    _inherit = 'account.move'

    finance_confirmed = fields.Boolean(string='Finance Confirmed', copy=False, tracking=True)
    finance_confirmed_by = fields.Many2one('res.users', readonly=True, copy=False)
    finance_confirmed_date = fields.Datetime(readonly=True, copy=False)
    vendor_invoice_reference = fields.Char(
        string='Vendor Invoice No.',
        help='Physical / emailed vendor invoice reference matched by Finance before posting.')
    finance_match_remarks = fields.Text(string='Finance Matching Remarks')

    forwarded_to_treasury = fields.Boolean(string='Forwarded to Treasury', copy=False, tracking=True)
    treasury_forwarded_by = fields.Many2one('res.users', readonly=True, copy=False)
    treasury_forwarded_date = fields.Datetime(readonly=True, copy=False)
    treasury_user_id = fields.Many2one(
        'res.users', string='Assigned Treasury Officer', copy=False,
        help='Optional explicit assignment; if blank, any Treasury group member can act.')

    def action_finance_confirm_and_post(self):
        """Finance matches the draft bill against the physical vendor invoice, then posts it."""
        self.ensure_one()
        if self.move_type != 'in_invoice':
            raise ValidationError(_('This action only applies to vendor bills.'))
        if not self.env.user.has_group('bn_procurement_finance.group_finance'):
            raise ValidationError(_('Only Finance users can confirm vendor bills.'))
 
        self.write({
            'finance_confirmed': True,
            'finance_confirmed_by': self.env.user.id,
            'finance_confirmed_date': fields.Datetime.now(),
        })
        self.action_post()
        return True

    def _post(self, soft=True):
        posted = super()._post(soft)
        posted.filtered(lambda move: move.move_type == 'in_invoice')._apply_po_advance_payments()
        return posted

    def _apply_po_advance_payments(self):
        """Deduct the advance already paid on the bill's Purchase Order(s), so the
        vendor is only paid the remainder. An advance that is still a draft cannot
        be deducted yet: it is when it gets posted."""
        for bill in self:
            orders = bill.line_ids.purchase_line_id.order_id
            if not orders:
                continue
            # sudo: whoever posts the bill may not be allowed to read payments.
            payments = self.env['account.payment'].sudo().search([('purchase_order_id', 'in', orders.ids)])
            payments.filtered(lambda p: p.state == 'posted')._reconcile_po_advance(bills=bill)
            draft = payments.filtered(lambda p: p.state == 'draft')
            if draft:
                bill.message_post(body=_(
                    'An advance payment of %(amount)s for %(orders)s is still in draft and is not deducted '
                    'from this bill yet. It is deducted automatically once Finance posts it.',
                    amount=', '.join(format_amount(self.env, p.amount, p.currency_id) for p in draft),
                    orders=', '.join(draft.purchase_order_id.mapped('name'))))

    # ------------------------------------------------------------------
    # No manual allocation of outstanding payments
    # ------------------------------------------------------------------
    def _is_purchase_order_bill(self):
        """Whether this is the vendor bill of a Purchase Order."""
        self.ensure_one()
        return self.move_type == 'in_invoice' and bool(self.line_ids.purchase_line_id)

    def _compute_payments_widget_to_reconcile_info(self):
        """The advance of a Purchase Order is deducted from the bill of that order
        automatically (_apply_po_advance_payments). So the bill of a Purchase Order
        offers no outstanding payment to allocate by hand, and the advance payment
        of an order is never offered on any other bill."""
        super()._compute_payments_widget_to_reconcile_info()
        for move in self:
            widget = move.invoice_outstanding_credits_debits_widget
            if not widget:
                continue
            content = []
            if not move._is_purchase_order_bill():
                # sudo: whoever opens the bill may not be allowed to read payments.
                advances = self.env['account.payment'].sudo().browse(
                    [vals['account_payment_id'] for vals in widget['content'] if vals['account_payment_id']]
                ).filtered('purchase_order_id')
                content = [vals for vals in widget['content'] if vals['account_payment_id'] not in advances.ids]
            if content:
                move.invoice_outstanding_credits_debits_widget = dict(widget, content=content)
            else:
                move.invoice_outstanding_credits_debits_widget = False
                move.invoice_has_outstanding = False

    def js_assign_outstanding_line(self, line_id):
        # The widget no longer offers these lines; this keeps them from being allocated another way.
        self.ensure_one()
        if self._is_purchase_order_bill():
            raise UserError(_(
                'Outstanding payments cannot be allocated by hand to the bill of a Purchase Order: '
                'the advance paid on the order is deducted from it automatically.'))
        # sudo: whoever opens the bill may not be allowed to read payments.
        advance = self.env['account.move.line'].browse(line_id).sudo().payment_id.filtered('purchase_order_id')
        if advance:
            raise UserError(_(
                'This is the advance payment of Purchase Order %s. It is deducted automatically from the '
                'bill of that order and cannot be allocated to another bill.',
                ', '.join(advance.purchase_order_id.mapped('display_name'))))
        return super().js_assign_outstanding_line(line_id)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_po_advance_payment(self):
        # force_delete: the payment itself is being deleted, which has its own check.
        if self.env.context.get('force_delete'):
            return
        for move in self:
            payment = move.sudo().payment_id
            if payment.purchase_order_id and move.state != 'cancel':
                raise UserError(_(
                    'This is the journal entry of the advance payment of Purchase Order %s and cannot be '
                    'deleted. Cancel the payment instead.', payment.purchase_order_id.display_name))


