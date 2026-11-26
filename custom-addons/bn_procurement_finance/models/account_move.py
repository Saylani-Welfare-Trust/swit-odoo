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

    grn_ids = fields.Many2many(
        'stock.picking', 
        string='Receipts (GRN)', 
        compute='_compute_grn_ids',
        help="Goods Receipt Notes associated with the Purchase Orders of this bill."
    )
    grn_count = fields.Integer(
        string='Receipt Count', 
        compute='_compute_grn_ids'
    )
    # stored (and tracked) on its own: a GRN validated after the bill updates it
    grn_reference = fields.Char(
        string='GRN Reference',
        compute='_compute_grn_reference',
        store=True,
        tracking=True,
        help="Comma-separated references of the related Goods Receipt Notes."
    )

    @api.depends('line_ids.purchase_line_id.order_id.picking_ids')
    def _compute_grn_ids(self):
        for move in self:
            if move.move_type == 'in_invoice':
                orders = move.line_ids.purchase_line_id.order_id
                pickings = orders.mapped('picking_ids').filtered(
                    lambda p: p.picking_type_code == 'incoming' and p.state == 'done'
                )
                move.grn_ids = pickings
                move.grn_count = len(pickings)
            else:
                move.grn_ids = False
                move.grn_count = 0

    @api.depends('move_type', 'line_ids.purchase_line_id.order_id.picking_ids.state',
                 'line_ids.purchase_line_id.order_id.picking_ids.name')
    def _compute_grn_reference(self):
        for move in self:
            move.grn_reference = ', '.join(move.grn_ids.mapped('name')) if move.move_type == 'in_invoice' else False

    def action_finance_confirm_and_post(self):
        """Finance matches the bill against the physical vendor invoice, then
        posts it (a draft bill) and forwards it to Treasury: only a bill of a
        Purchase Order forwarded this way can be paid. A bill already posted
        without the Finance check is confirmed and forwarded the same way."""
        self.ensure_one()
        if self.move_type != 'in_invoice':
            raise ValidationError(_('This action only applies to vendor bills.'))
        if not self.env.su and not self.env.user.has_group('bn_procurement_finance.group_finance'):
            raise ValidationError(_('Only Finance users can confirm vendor bills.'))
        if self.state == 'cancel':
            raise UserError(_('%s is cancelled: it cannot be confirmed.') % self.display_name)
        if self.finance_confirmed:
            raise UserError(_('%s is already confirmed by Finance.') % self.display_name)

        now = fields.Datetime.now()
        self.write({
            'finance_confirmed': True,
            'finance_confirmed_by': self.env.user.id,
            'finance_confirmed_date': now,
            'forwarded_to_treasury': True,
            'treasury_forwarded_by': self.env.user.id,
            'treasury_forwarded_date': now,
        })

        # Post a specific message to the chatter with the GRN reference
        grn_msg = _("Finance Confirmed & Posted, forwarded to Treasury.") if self.state == 'draft' \
            else _("Finance Confirmed, forwarded to Treasury.")
        if self.grn_reference:
            grn_msg += _(" Linked GRN(s): %s", self.grn_reference)
        self.message_post(body=grn_msg)

        if self.state == 'draft':
            self.action_post()
        return True

    def action_bulk_set_date_reference(self):
        """Open the wizard to set the bill date and vendor invoice reference on
        all selected vendor bills in one go."""
        if not self:
            raise UserError(_('Please select at least one vendor bill first.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bulk Set Bill Date & Reference'),
            'res_model': 'bulk.bill.date.reference.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_ids': self.ids,
                'active_model': 'account.move',
            },
        }

    def _check_treasury_payable(self):
        """A bill of a Purchase Order is paid only once Finance has confirmed it
        and forwarded it to Treasury, and only by its assigned Treasury officer
        when one is set."""
        if self.env.su:
            return
        for bill in self.filtered(lambda m: m.move_type == 'in_invoice' and m._is_purchase_order_bill()):
            if not bill.forwarded_to_treasury:
                raise UserError(_(
                    '%s is not confirmed by Finance yet: Finance must match it with the vendor invoice '
                    '(Finance Confirm & Post) before it can be paid.') % bill.display_name)
            if bill.treasury_user_id and bill.treasury_user_id != self.env.user:
                raise UserError(_('%(bill)s is assigned to the Treasury officer %(user)s.',
                                  bill=bill.display_name, user=bill.treasury_user_id.name))

    def action_view_grn(self):
        """Action to open the list of linked Goods Receipt Notes."""
        self.ensure_one()
        # Use the standard incoming receipt action
        action = self.env['ir.actions.act_window']._for_xml_id('stock.action_picking_tree_incoming')
        action['domain'] = [('id', 'in', self.grn_ids.ids)]
        action['context'] = {}
        return action

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
    # Advance payments stay on the bills of their own Purchase Order
    # ------------------------------------------------------------------
    def _is_purchase_order_bill(self):
        """Whether this is the vendor bill of a Purchase Order."""
        self.ensure_one()
        return self.move_type == 'in_invoice' and bool(self.line_ids.purchase_line_id)

    def _foreign_po_advances(self, payments):
        """The advance payments among ``payments`` that belong to a Purchase Order
        other than this bill's. Only those may not be allocated to this bill: any
        other outstanding payment (e.g. one unreconciled from this bill) can be
        added back by hand instead of registering a second payment."""
        self.ensure_one()
        own_orders = self.line_ids.purchase_line_id.order_id
        # sudo: whoever opens the bill may not be allowed to read payments.
        return payments.sudo().filtered(
            lambda p: p.purchase_order_id and p.purchase_order_id not in own_orders)

    def _compute_payments_widget_to_reconcile_info(self):
        """The advance of a Purchase Order is deducted from the bill of that order
        automatically (_apply_po_advance_payments), and is never offered on the
        bill of another order or on a bill without one."""
        if self.env.context.get('bin_size'):
            # The web client reads with bin_size, and reading a Binary field back with
            # bin_size gives False (see fields.Binary.compute_value): the widget would
            # be emptied below. Compute without it and copy the result over.
            moves = self.with_context(bin_size=False)
            moves._compute_payments_widget_to_reconcile_info()
            for move, computed in zip(self, moves):
                move.invoice_outstanding_credits_debits_widget = computed.invoice_outstanding_credits_debits_widget
                move.invoice_has_outstanding = computed.invoice_has_outstanding
            return
        super()._compute_payments_widget_to_reconcile_info()
        for move in self:
            widget = move.invoice_outstanding_credits_debits_widget
            if not widget:
                continue
            blocked = move._foreign_po_advances(self.env['account.payment'].browse(
                [vals['account_payment_id'] for vals in widget['content'] if vals['account_payment_id']]))
            content = [vals for vals in widget['content'] if vals['account_payment_id'] not in blocked.ids]
            if content:
                move.invoice_outstanding_credits_debits_widget = dict(widget, content=content)
            else:
                move.invoice_outstanding_credits_debits_widget = False
                move.invoice_has_outstanding = False

    def js_assign_outstanding_line(self, line_id):
        # The widget no longer offers these lines; this keeps them from being allocated another way.
        self.ensure_one()
        advance = self._foreign_po_advances(self.env['account.move.line'].browse(line_id).sudo().payment_id)
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


