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


