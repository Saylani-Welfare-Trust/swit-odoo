from odoo.exceptions import AccessError, UserError
from odoo.tools import float_is_zero
from odoo import models, fields, _
import logging

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.session'

    # ------------------------------------------------------------
    # CUSTOM FIELDS
    # ------------------------------------------------------------
    restricted_category = fields.Char(related='company_id.restricted_category', readonly=True)
    unrestricted_category = fields.Char(related='company_id.unrestricted_category', readonly=True)

    # ------------------------------------------------------------
    # OVERRIDE _get_closed_orders
    # ------------------------------------------------------------
    def _get_closed_orders(self):
        # Every order whose money was taken: like Odoo, minus the refunds
        # still waiting for CFO approval or rejected (bn_pos_order).
        return self.order_ids.filtered(lambda o: o.state not in ('draft', 'cancel', 'cfo_approval', 'reject'))

    # ------------------------------------------------------------
    # DATA COMPUTATION FOR THE CLOSING POPUP
    # ------------------------------------------------------------
    def _compute_closing_details(self):
        self.ensure_one()
        orders = self._get_closed_orders()
        breakdown = {}
        for order in orders:
            order_rest = order_unrest = order_neutral = 0.0
            for line in order.lines:
                restriction = self._is_restricted_product(line.product_id)
                if restriction == 1:
                    order_rest += line.price_subtotal_incl
                elif restriction == 2:
                    order_unrest += line.price_subtotal_incl
                else:
                    order_neutral += line.price_subtotal_incl
            total = order_rest + order_unrest + order_neutral
            if float_is_zero(total, precision_rounding=self.currency_id.rounding):
                continue
            ratios = (order_rest / total, order_unrest / total, order_neutral / total)
            for payment in order.payment_ids:
                pm_id = payment.payment_method_id.id
                if pm_id not in breakdown:
                    breakdown[pm_id] = {'restricted': 0.0, 'unrestricted': 0.0, 'neutral': 0.0}
                breakdown[pm_id]['restricted'] += payment.amount * ratios[0]
                breakdown[pm_id]['unrestricted'] += payment.amount * ratios[1]
                breakdown[pm_id]['neutral'] += payment.amount * ratios[2]
        return breakdown

    def _is_restricted_product(self, product):
        if not product.categ_id:
            return 0
        cat_name = (product.categ_id.complete_name or '').lower()
        # an empty setting matches nothing (not every category)
        restricted = (self.company_id.restricted_category or '').strip().lower()
        unrestricted = (self.company_id.unrestricted_category or '').strip().lower()
        if unrestricted and unrestricted in cat_name:
            return 2
        if restricted and restricted in cat_name:
            return 1
        return 0

    def get_closing_control_data(self):
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("You don't have the access rights to get the point of sale closing control data."))
        self.ensure_one()

        orders = self._get_closed_orders()
        payments = orders.payment_ids.filtered(lambda p: p.payment_method_id.type != "pay_later")
        cash_methods = self.payment_method_ids.filtered(lambda pm: pm.type == 'cash')
        default_cash = cash_methods[0] if cash_methods else None
        total_cash = sum(payments.filtered(lambda p: p.payment_method_id == default_cash).mapped('amount')) if default_cash else 0

        last_session = self.search([('config_id', '=', self.config_id.id), ('id', '!=', self.id)], limit=1)
        cash_moves = self.sudo().statement_line_ids.sorted('create_date')
        cash_in_out = [{'name': f'Cash in {i+1}' if move.amount > 0 else f'Cash out {i+1}',
                        'amount': move.amount} for i, move in enumerate(cash_moves)]

        breakdown = self._compute_closing_details()
        slip_methods = self._bn_slip_methods()
        default_cash_details = None
        if default_cash:
            default_cash_details = {
                'name': default_cash.name,
                'amount': (last_session.cash_register_balance_end_real + total_cash +
                           sum(cash_moves.mapped('amount'))),
                'opening': last_session.cash_register_balance_end_real,
                'payment_amount': total_cash,
                'moves': cash_in_out,
                'id': default_cash.id,
                'breakdown': breakdown.get(default_cash.id, {'restricted': 0.0, 'unrestricted': 0.0, 'neutral': 0.0}),
                'skip_amount_input': default_cash.skip_amount_input,
                'use_slips': default_cash in slip_methods,
            }

        other_methods = []
        for pm in self.payment_method_ids - (default_cash if default_cash else self.env['pos.payment.method']):
            pm_payments = orders.payment_ids.filtered(lambda p: p.payment_method_id == pm)
            other_methods.append({
                'name': pm.name,
                'amount': sum(pm_payments.mapped('amount')),
                'number': len(pm_payments),
                'id': pm.id,
                'type': pm.type,
                'breakdown': breakdown.get(pm.id, {'restricted': 0.0, 'unrestricted': 0.0, 'neutral': 0.0}),
                'skip_amount_input': pm.skip_amount_input,
                'use_slips': pm in slip_methods,
            })

        banks = [{'id': bank.id, 'name': bank.name} for bank in self.env['account.journal'].search([('show_in_pos', '=', True)])]

        return {
            'orders_details': {'quantity': len(orders), 'amount': sum(orders.mapped('amount_total'))},
            'opening_notes': self.opening_notes,
            'default_cash_details': default_cash_details,
            'other_payment_methods': other_methods,
            'is_manager': self.user_has_groups("point_of_sale.group_pos_manager"),
            'amount_authorized_diff': self.config_id.amount_authorized_diff if self.config_id.set_maximum_difference else None,
            'bank_list': banks,
        }

    # ------------------------------------------------------------
    # SPLIT ACCOUNTING (deposit slips)
    # ------------------------------------------------------------
    # The money of the "slip" payment methods (cash and bank ones, unless
    # they split their transactions or skip the amount input) is deposited
    # by slip, one per category: restricted / unrestricted / non-donation.
    #   - cash: Odoo's own cash flow is kept (the sales enter the cash
    #     journal and clear the POS receivable); the deposited slips then
    #     leave the cash journal as cash-out lines to the category accounts,
    #     so the drawer keeps only what was counted;
    #   - bank: no combined payment, the session entry debits the category
    #     accounts instead of the POS receivable.
    # The other methods (pay later, split transactions, skip amount input)
    # follow the standard Odoo flow.
    SLIP_TYPES = ('restricted', 'unrestricted', 'neutral')

    def _bn_slip_methods(self):
        # cash is counted (and so deposited by slip) only with cash control
        return self.payment_method_ids.filtered(
            lambda pm: (pm.type == 'bank' or (pm.type == 'cash' and self.config_id.cash_control))
            and not pm.split_transactions and not pm.skip_amount_input)

    def _get_restricted_receivable_account(self, payment_method):
        return (payment_method.restricted_account_id or
                self.company_id.account_default_pos_restricted_receivable_account_id)

    def _get_neutral_receivable_account(self, payment_method):
        return (payment_method.neutral_account_id or
                self.company_id.account_default_pos_neutrnal_receivable_account_id)

    def _get_unrestricted_receivable_account(self, payment_method):
        return (payment_method.unrestricted_account_id or
                self.company_id.account_default_pos_unrestricted_receivable_account_id)

    def _bn_slip_account_label(self, payment_method, slip_type):
        if slip_type == 'restricted':
            return (self._get_restricted_receivable_account(payment_method),
                    self.company_id.restricted_category or _('Restricted'))
        if slip_type == 'unrestricted':
            return (self._get_unrestricted_receivable_account(payment_method),
                    self.company_id.unrestricted_category or _('Unrestricted'))
        return self._get_neutral_receivable_account(payment_method), _('Non Donation')

    def _bn_parse_slips(self, lines):
        """{payment method: [(type, amount, ref, bank_id)]} of the slip
        methods, checked against what each method took."""
        rounding = self.currency_id.rounding
        slip_methods = self._bn_slip_methods()
        payments = self._get_closed_orders().payment_ids
        slips = {}
        for pm_id, vals in (lines or {}).items():
            pm = self.env['pos.payment.method'].browse(int(pm_id))
            if pm not in slip_methods:
                continue
            for slip_type in self.SLIP_TYPES:
                for entry in (vals or {}).get(slip_type) or []:
                    amount = entry.get('amount') or 0.0
                    if float_is_zero(amount, precision_rounding=rounding):
                        continue
                    bank = entry.get('bank')
                    slips.setdefault(pm, []).append((
                        slip_type, amount, entry.get('ref') or '',
                        int(bank) if bank and str(bank) != '0' else False))
        for pm in slip_methods:
            expected = sum(payments.filtered(lambda p: p.payment_method_id == pm).mapped('amount'))
            deposited = sum(slip[1] for slip in slips.get(pm, []))
            if not float_is_zero(expected - deposited, precision_rounding=rounding):
                raise UserError(_(
                    "%(method)s: the deposit slips total %(slips)s but the payments total %(expected)s.\n"
                    "Please add a slip for each category.",
                    method=pm.name, slips=self.currency_id.round(deposited),
                    expected=self.currency_id.round(expected)))
            for slip_type, amount, ref, bank_id in slips.get(pm, []):
                account, label = self._bn_slip_account_label(pm, slip_type)
                if not account:
                    raise UserError(_("No account defined for %s (%s).", pm.name, label))
        return slips

    def _bn_create_cash_deposits(self, slips):
        """The cash deposited by slip leaves the cash journal."""
        for pm, pm_slips in slips.items():
            if pm.type != 'cash':
                continue
            for slip_type, amount, ref, bank_id in pm_slips:
                account, label = self._bn_slip_account_label(pm, slip_type)
                self.env['account.bank.statement.line'].sudo().create({
                    'pos_session_id': self.id,
                    'journal_id': pm.journal_id.id,
                    'amount': -amount,
                    'date': fields.Date.context_today(self),
                    'payment_ref': ' - '.join(filter(None, [self.name, label, pm.name, ref])),
                    'counterpart_account_id': account.id,
                })

    def _bn_create_bank_slip_lines(self, slips):
        """The bank money deposited by slip: debit the category accounts."""
        MoveLine = self.env['account.move.line'].with_context(check_move_validity=False)
        for pm, pm_slips in slips.items():
            if pm.type != 'bank':
                continue
            for slip_type, amount, ref, bank_id in pm_slips:
                account, label = self._bn_slip_account_label(pm, slip_type)
                MoveLine.create({
                    'move_id': self.move_id.id,
                    'name': ' - '.join(filter(None, [self.name, label, pm.name, ref])),
                    'account_id': account.id,
                    'debit': amount if amount > 0 else 0.0,
                    'credit': -amount if amount < 0 else 0.0,
                    'partner_id': False,
                    'bank_journal_id': bank_id,
                })

    def _create_bank_payment_moves(self, data):
        """Bank slip methods: no combined receivable line nor payment, the
        slips debit the category accounts instead."""
        if not self.env.context.get('bn_slip_closing'):
            return super()._create_bank_payment_moves(data)
        slip_methods = self._bn_slip_methods()
        combine = data.get('combine_receivables_bank') or {}
        data['combine_receivables_bank'] = {pm: amounts for pm, amounts in combine.items() if pm not in slip_methods}
        data = super()._create_bank_payment_moves(data)
        data['combine_receivables_bank'] = combine
        return data

    def _reconcile_account_move_lines(self, data):
        """Defensively ensure all required keys exist before calling super."""
        if data is None:
            data = {}
        for key in ('payment_method_to_receivable_lines', 'split_cash_statement_lines',
                    'combine_cash_statement_lines', 'split_cash_receivable_lines',
                    'combine_cash_receivable_lines', 'stock_output_lines', 'payment_to_receivable_lines'):
            if data.get(key) is None:
                data[key] = {}
        return super()._reconcile_account_move_lines(data)

    # ------------------------------------------------------------
    # CLOSING FLOW OVERRIDES (pass lines correctly)
    # ------------------------------------------------------------
    def _validate_session(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None, lines=None):
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        self.ensure_one()
        data = {}
        sudo = self.user_has_groups('point_of_sale.group_pos_user')

        if self.order_ids.filtered(lambda o: o.state != 'cancel') or self.sudo().statement_line_ids:
            if self.state == 'closed':
                raise UserError(_('This session is already closed.'))
            self._check_if_no_draft_orders()
            self._bn_check_no_pending_refunds()
            self._check_invoices_are_posted()

            slips = self._bn_parse_slips(lines)
            # before the cash difference: the deposited cash is not missing
            self._bn_create_cash_deposits(slips)
            # the bank slip methods have no counted amount of their own
            slip_methods = self._bn_slip_methods()
            bank_payment_method_diffs = {pm_id: diff for pm_id, diff in bank_payment_method_diffs.items()
                                         if pm_id not in slip_methods.ids}

            self.cash_real_transaction = sum(self.sudo().statement_line_ids.mapped('amount'))
            cash_difference_before = self.cash_register_difference

            if self.update_stock_at_closing:
                self._create_picking_at_end_of_session()
                self._get_closed_orders().filtered(lambda o: not o.is_total_cost_computed)._compute_total_cost_at_session_closing(self.picking_ids.move_ids)

            def create_move(session):
                move_data = super(PosSession, session.with_context(bn_slip_closing=True))._create_account_move(
                    balancing_account, amount_to_balance, bank_payment_method_diffs)
                session.with_company(session.company_id)._bn_create_bank_slip_lines(slips)
                return move_data

            try:
                with self.env.cr.savepoint():
                    data = create_move(self.with_company(self.company_id).with_context(
                        check_move_validity=False, skip_invoice_sync=True))
            except AccessError as e:
                if sudo:
                    data = create_move(self.sudo().with_company(self.company_id).with_context(
                        check_move_validity=False, skip_invoice_sync=True))
                else:
                    raise e

            if data is None:
                data = {}

            balance = sum(self.move_id.line_ids.mapped('balance'))
            try:
                with self.move_id._check_balanced({'records': self.move_id.sudo()}):
                    pass
            except UserError:
                self.env.cr.rollback()
                return self._close_session_action(balance)

            self.sudo()._post_statement_difference(cash_difference_before, False)

            if self.move_id.line_ids:
                self.move_id.sudo().with_company(self.company_id)._post()
                for dummy, amount_data in data.get('sales', {}).items():
                    self.env['account.move.line'].browse(amount_data['move_line_id']).sudo().with_company(self.company_id).write({
                        'price_subtotal': abs(amount_data['amount_converted']),
                        'price_total': abs(amount_data['amount_converted']) + abs(amount_data['tax_amount']),
                    })
                self.env['pos.order'].search([('session_id', '=', self.id), ('state', '=', 'paid')]).write({'state': 'done'})
            else:
                self.move_id.sudo().unlink()
            self.sudo().with_company(self.company_id)._reconcile_account_move_lines(data)
        else:
            self.sudo()._post_statement_difference(self.cash_register_difference, False)

        self.write({'state': 'closed'})
        return True

    def _bn_check_no_pending_refunds(self):
        """A refund waiting for the CFO has not been decided: closing now would
        leave it out of every session's entry once approved."""
        pending = self.order_ids.filtered(lambda o: o.state == 'cfo_approval')
        if pending:
            raise UserError(_(
                "Refunds waiting for CFO approval: %s. The CFO must approve or reject them before "
                "the session can be closed.", ', '.join(pending.mapped('name'))))

    def action_pos_session_closing_control(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None, lines=None):
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        for session in self:
            if any(order.state == 'draft' for order in session.order_ids):
                raise UserError(_("You cannot close the POS when orders are still in draft"))
            if session.state == 'closed':
                raise UserError(_('This session is already closed.'))
            session.write({'state': 'closing_control', 'stop_at': fields.Datetime.now()})
            if not session.config_id.cash_control:
                return session.action_pos_session_close(balancing_account, amount_to_balance, bank_payment_method_diffs, lines)
            default_cash = session.payment_method_ids.filtered(lambda pm: pm.type == 'cash')[:1]
            if session.rescue and default_cash:
                orders = session._get_closed_orders()
                total_cash = sum(orders.payment_ids.filtered(lambda p: p.payment_method_id == default_cash).mapped('amount')) + session.cash_register_balance_start
                session.cash_register_balance_end_real = total_cash
            return session.action_pos_session_validate(balancing_account, amount_to_balance, bank_payment_method_diffs, lines)

    def action_pos_session_validate(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None, lines=None):
        return self.action_pos_session_close(balancing_account, amount_to_balance, bank_payment_method_diffs, lines)

    def action_pos_session_close(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None, lines=None):
        return self._validate_session(balancing_account, amount_to_balance, bank_payment_method_diffs, lines)

    def close_session_from_ui(self, bank_payment_method_diff_pairs=None, lines=None, cash_counted=None):
        """Closing popup. ``cash_counted``: the cash left in the drawer once
        the slips are deposited (the next session opens with it)."""
        self.ensure_one()
        slip_method_ids = self._bn_slip_methods().ids
        bank_diffs = {pm_id: diff for pm_id, diff in dict(bank_payment_method_diff_pairs or []).items()
                      if pm_id not in slip_method_ids}
        check = self._cannot_close_session(bank_diffs)
        if check:
            return check
        if cash_counted is not None and self.config_id.cash_control and self.cash_journal_id:
            try:
                self.cash_register_balance_end_real = float(cash_counted or 0.0)
            except (TypeError, ValueError):
                return {'successful': False, 'message': _('The counted cash is not a number.'), 'redirect': False}
        try:
            result = self.action_pos_session_closing_control(bank_payment_method_diffs=bank_diffs, lines=lines)
        except UserError as e:
            self.env.cr.rollback()
            return {
                'successful': False,
                'message': e.args[0] if e.args else str(e),
                'redirect': False
            }
        if isinstance(result, dict):
            return result
        self._message_log(body=_("Point of Sale Session ended"))
        return {"successful": True}

    def show_session_slip(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Deposit Slips'),
            'res_model': 'pos.session.slip',
            'domain': [('session_id', '=', self.id)],
            'view_mode': 'tree,form',
            'target': 'current',
        }

    def _loader_params_res_company(self):
        vals = super()._loader_params_res_company()
        vals['search_params']['fields'] += ['restricted_category', 'unrestricted_category']
        return vals
