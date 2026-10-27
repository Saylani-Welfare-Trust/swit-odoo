import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

TREASURY_GROUP = 'bn_pos_cheque.pos_cheque_menu_group'
POS_GROUP = 'bn_pos_cheque.pos_cheque_pos_action_group'

# A cheque can bounce this many times; after that it can only be settled
# (given back to the donor) at the POS.
MAX_BOUNCES = 4

state_selection = [
    ('draft', 'Draft'),
    ('clear', 'Clear'),
    ('bounce', 'Bounce'),
    ('cancel', 'Cancelled'),
]

# pos.session._is_restricted_product() result -> slip type used on the closing screen
SLIP_TYPES = {1: 'restricted', 2: 'unrestricted', 0: 'neutral'}


class POSCheque(models.Model):
    _name = 'pos.cheque'
    _description = "POS Cheque"
    _order = 'id desc'

    bank_id = fields.Many2one('account.journal', string="Bank")
    donor_id = fields.Many2one('res.partner', string="Donor", compute="_set_details", store=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", compute="_set_details", store=True)
    name = fields.Char('Cheque Number')
    state = fields.Selection(selection=state_selection, string="State", default='draft')
    order_reference = fields.Char('Order Reference', compute="_set_details", store=True)
    bank_name = fields.Char('Bank Name')
    date = fields.Date('Cheque Date')
    bounce_count = fields.Integer('Bounce Count')
    amount = fields.Float('Amount', compute="_set_details", store=True)
    # Program modules add their own values (bn_welfare, bn_medical_equipment)
    source_model = fields.Selection([], string="Source Type")

    move_id = fields.Many2one('account.move', string="Journal Entry", readonly=True)
    source_record_id = fields.Integer(string="Source Record ID")

    @api.depends('name')
    def _set_details(self):
        for rec in self:
            rec.donor_id = None
            rec.analytic_account_id = None
            rec.amount = 0
            rec.order_reference = ''
            pos_order = rec._get_pos_order()
            if pos_order:
                rec.donor_id = pos_order.partner_id.id
                rec.analytic_account_id = pos_order.analytic_account_id.id
                rec.amount = pos_order.amount_total
                branch_code = pos_order.user_id.employee_id.analytic_account_id.code
                company = pos_order.company_id.name[:3].upper()
                order_date = pos_order.date_order and pos_order.date_order.year or ''
                order_ref = pos_order.name and pos_order.name[-4:] or '0000'
                rec.order_reference = f'{branch_code}-{company}-{order_date}-{order_ref}'

    def _get_pos_order(self):
        self.ensure_one()
        if not self.id:
            return self.env['pos.order']
        return self.env['pos.order'].sudo().search([('pos_cheque_id', '=', self.id)], limit=1)

    def action_show_pos_order(self):
        self.ensure_one()
        return {
            'name': 'POS Order',
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'context': {'edit': '0', 'delete': '0'},
            'view_mode': 'form',
            'res_id': self._get_pos_order().id,
            'target': 'new',
        }

    def action_print_receipt(self):
        """Donation receipt of the linked POS order. Only once the cheque is
        cleared - until then the donor holds the provisional slip from POS."""
        self.ensure_one()
        if self.state != 'clear':
            raise ValidationError('The donation receipt can be printed only after the cheque is cleared.')

        pos_order = self._get_pos_order()
        if not pos_order:
            raise ValidationError('No POS order is linked to this cheque.')

        # the clean (non-duplicate) receipt, same one the donor gets on WhatsApp
        action = self.env.ref('bn_pos_order.pos_whatsapp_donation_receipt_report').report_action(pos_order)
        action['name'] = 'Donation Receipt'
        return action

    def _send_clear_notification(self):
        """WhatsApp / SMS the donation receipt of the linked POS order. POS
        holds this message back for cheque orders until the cheque is cleared
        (see pos.order.sms_or_whatsapp_send_receipt)."""
        self.ensure_one()
        pos_order = self._get_pos_order()
        if not pos_order:
            return

        # a failed message must never block the clearing itself
        try:
            with self.env.cr.savepoint():
                pos_order.send_whatsapp_after_payment(pos_order.id)
        except Exception as e:
            _logger.error('Cheque %s: clear notification failed: %s', self.name, str(e))

    # ---------- ACCOUNTING ----------
    def _get_clearing_account(self, order, payment):
        """Account the cheque sits in until it is cleared: the company's
        *Cheque Clearing Account* if set, else the receivable account the
        session closing posted the cheque to (bn_closing_session)."""
        company = order.company_id
        if company.pos_cheque_clearing_account_id:
            return company.pos_cheque_clearing_account_id
        session = order.session_id
        payment_method = payment.payment_method_id
        amounts = {}
        for line in order.lines:
            slip_type = SLIP_TYPES[session._is_restricted_product(line.product_id)]
            amounts[slip_type] = amounts.get(slip_type, 0.0) + line.price_subtotal_incl
        slip_type = max(amounts, key=amounts.get) if amounts else 'neutral'
        getter = {
            'restricted': session._get_restricted_receivable_account,
            'unrestricted': session._get_unrestricted_receivable_account,
            'neutral': session._get_neutral_receivable_account,
        }[slip_type]
        return (getter(payment_method)
                or payment_method.outstanding_account_id
                or company.account_journal_payment_debit_account_id)

    def _create_bank_deposit_entry(self):
        """Move the cheque amount from the clearing account to the bank of
        the deposit (Treasury > POS Cheque > Deposit to Bank)."""
        self.ensure_one()
        if self.move_id:
            return
        if not self.bank_id:
            raise UserError(_('Select the bank the cheque %s was deposited to (Deposit to Bank) before clearing it.') % self.name)

        order = self._get_pos_order()
        if not order or not order.payment_ids:
            _logger.warning("No POS order or payments found for cheque %s", self.name)
            return

        # the cheque payment of the order (an order can be split over methods)
        cheque_payment = order.payment_ids.filtered(
            lambda p: p.payment_method_id.type == 'bank' or 'cheque' in (p.payment_method_id.name or '').lower()
        )[:1] or order.payment_ids[:1]

        clearing_account = self._get_clearing_account(order, cheque_payment)
        bank_account = self.bank_id.default_account_id
        if not clearing_account or not bank_account:
            raise UserError(_(
                "Cannot post the deposit of cheque %s: the bank journal needs a default account, and a "
                "Cheque Clearing Account (Accounting settings) or the payment method's receivable account "
                "must be set.") % self.name)

        analytic_dist = {str(self.analytic_account_id.id): 100} if self.analytic_account_id else {}
        partner_id = self.donor_id.id or False
        label = _("Cheque Deposit %s") % self.name
        move = self.env['account.move'].sudo().create({
            'move_type': 'entry',
            'journal_id': self.bank_id.id,
            'date': fields.Date.context_today(self),
            'ref': f"{label} - {order.name}",
            'partner_id': partner_id,
            'line_ids': [
                (0, 0, {'name': label, 'account_id': bank_account.id, 'debit': self.amount, 'credit': 0.0,
                        'partner_id': partner_id, 'analytic_distribution': analytic_dist}),
                (0, 0, {'name': label, 'account_id': clearing_account.id, 'debit': 0.0, 'credit': self.amount,
                        'partner_id': partner_id, 'analytic_distribution': analytic_dist}),
            ],
        })
        move.action_post()
        self.move_id = move.id

        # Reconcile with the receivable line of the same donor and amount, if
        # the clearing account allows it and such a line exists.
        if clearing_account.reconcile:
            clearing_line = move.line_ids.filtered(lambda l: l.account_id == clearing_account)
            pos_line = self.env['account.move.line'].sudo().search([
                ('account_id', '=', clearing_account.id),
                ('partner_id', '=', partner_id),
                ('debit', '=', self.amount),
                ('reconciled', '=', False),
                ('parent_state', '=', 'posted'),
            ], limit=1)
            if pos_line:
                (clearing_line + pos_line).reconcile()

    # ---------- LIFECYCLE ----------
    # Program modules (bn_advance_donation, bn_microfinance, bn_welfare,
    # bn_medical_equipment, bn_livestock_slaugther ...) extend action_clear /
    # action_bounce / action_cancel for their own records.
    def _check_cheque_state(self, allowed, action):
        labels = dict(state_selection)
        for rec in self:
            if rec.state not in allowed:
                raise UserError(_('"%(action)s" is not possible for cheque %(name)s in status "%(state)s".') % {
                    'action': action, 'name': rec.name, 'state': labels.get(rec.state, rec.state)})

    def _check_treasury(self):
        if not self.env.su and not self.env.user.has_group(TREASURY_GROUP):
            raise AccessError(_('Only Treasury users can clear or bounce cheques.'))

    def action_clear(self):
        self._check_treasury()
        self._check_cheque_state(('draft', 'bounce'), _('Clear'))
        for rec in self:
            if rec.bounce_count >= MAX_BOUNCES:
                raise UserError(_('Cheque %s bounced %s times: settle it at the POS instead.') % (rec.name, rec.bounce_count))
            rec._create_bank_deposit_entry()
            rec.state = 'clear'
            rec._send_clear_notification()
        return True

    def action_bounce(self):
        self._check_treasury()
        self._check_cheque_state(('draft',), _('Bounce'))
        for rec in self:
            if rec.bounce_count >= MAX_BOUNCES:
                raise UserError(_('A cheque cannot bounce more than %s times.') % MAX_BOUNCES)
            rec.bounce_count += 1
            rec.state = 'bounce'
        return True

    def action_redeposit(self):
        """A bounced cheque presented again (POS Cheques > Re-Deposit)."""
        self._check_cheque_state(('bounce',), _('Re-Deposit'))
        for rec in self:
            if rec.bounce_count >= MAX_BOUNCES:
                raise UserError(_('Cheque %s bounced %s times: settle it instead.') % (rec.name, rec.bounce_count))
            rec.state = 'draft'
        return True

    def action_cancel(self):
        """Settled at the POS: the cheque is given back to the donor."""
        self._check_cheque_state(('draft', 'bounce'), _('Settle'))
        self.write({'state': 'cancel'})
        return True
