from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare, float_is_zero
from odoo import models, fields, _, api
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
        return self.order_ids.filtered(lambda o: o.state in ['refund', 'paid'])

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

    def _compute_payment_breakdown_from_slips(self):
        slips = self.env['pos.session.slip'].search([('session_id', '=', self.id)])
        result = {}
        for slip in slips:
            pm_id = slip.pos_payment_method_id.id
            result.setdefault(pm_id, {'restricted': [], 'unrestricted': [], 'neutral': []})
            result[pm_id][slip.type].append({
                'amount': slip.amount,
                'ref': slip.ref,
                'bank_id': slip.bank_id.id if slip.bank_id else False,
            })
        return result

    def _is_restricted_product(self, product):
        if not product.categ_id:
            return 0
        cat_name = product.categ_id.complete_name.lower()
        restricted = self.company_id.restricted_category.lower()
        unrestricted = self.company_id.unrestricted_category.lower()
        if unrestricted in cat_name:
            return 2
        if restricted in cat_name:
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
            })

        banks = [{'id': bank.id, 'name': bank.name} for bank in self.env['account.journal'].search([]) if bank.show_in_pos]

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
    # HELPER METHODS FOR SPLIT ACCOUNTING
    # ------------------------------------------------------------
    def _get_receivable_account_type(self):
        """Return the account_type string of the company's default POS receivable account."""
        return self.company_id.account_default_pos_receivable_account_id.account_type

    def _get_restricted_receivable_account_type(self):
        return self.company_id.account_default_pos_restricted_receivable_account_id.account_type

    def _get_neutral_receivable_account_type(self):
        return self.company_id.account_default_pos_neutrnal_receivable_account_id.account_type

    def _get_unrestricted_receivable_account_type(self):
        return self.company_id.account_default_pos_unrestricted_receivable_account_id.account_type

    def _get_restricted_receivable_account(self, payment_method):
        return (payment_method.restricted_account_id or
                self.company_id.account_default_pos_restricted_receivable_account_id)

    def _get_neutral_receivable_account(self, payment_method):
        return (payment_method.neutral_account_id or
                self.company_id.account_default_pos_neutrnal_receivable_account_id)

    def _get_unrestricted_receivable_account(self, payment_method):
        return (payment_method.unrestricted_account_id or
                self.company_id.account_default_pos_unrestricted_receivable_account_id)

    def _extract_payment_method_id_from_line(self, line):
        name = line.name or ''
        for pm in self.payment_method_ids:
            if pm.name in name:
                return pm.id
        return self.payment_method_ids.filtered(lambda p: p.type == 'bank')[:1].id

    def _create_split_difference_lines(self, bank_payment_method_diffs, payment_breakdown):
        for pm_id, diff in bank_payment_method_diffs.items():
            if float_is_zero(diff, precision_rounding=self.currency_id.rounding):
                continue
            pm = self.env['pos.payment.method'].browse(pm_id)
            account = self._get_neutral_receivable_account(pm)
            if account:
                self.env['account.move.line'].with_context(
                    check_move_validity=False
                ).create({
                    'move_id': self.move_id.id,
                    'name': _("Bank difference - %s", pm.name),
                    'account_id': account.id,
                    'debit': diff if diff > 0 else 0,
                    'credit': -diff if diff < 0 else 0,
                    'partner_id': False,
                })

    # ------------------------------------------------------------
    # OVERRIDES TO STOP COMBINE BANK PAYMENT CREATION
    # ------------------------------------------------------------
    def _create_bank_payment_moves(self, data):
        """Override to skip combined bank payment moves when context flag is set."""
        if self.env.context.get('skip_combine_payment'):
            MoveLine = data.get('MoveLine')
            split_receivables_bank = data.get('split_receivables_bank', {})
            bank_payment_method_diffs = data.get('bank_payment_method_diffs', {})
            payment_to_receivable_lines = {}
            payment_method_to_receivable_lines = {}

            for payment, amounts in split_receivables_bank.items():
                split_receivable_line = MoveLine.create(
                    self._get_split_receivable_vals(payment, amounts['amount'], amounts['amount_converted'])
                )
                payment_receivable_line = self._create_split_account_payment(payment, amounts)
                payment_to_receivable_lines[payment] = split_receivable_line | payment_receivable_line

            for bank_payment_method in self.payment_method_ids.filtered(
                lambda pm: pm.type == 'bank' and pm.split_transactions
            ):
                self._create_diff_account_move_for_split_payment_method(
                    bank_payment_method, bank_payment_method_diffs.get(bank_payment_method.id) or 0
                )

            data['payment_to_receivable_lines'] = payment_to_receivable_lines
            data['payment_method_to_receivable_lines'] = payment_method_to_receivable_lines
            return data
        else:
            return super()._create_bank_payment_moves(data)

    def _create_combine_account_payment(self, payment_method, amounts, diff_amount):
        """Override to skip combined account payment creation when context flag is set."""
        if self.env.context.get('skip_combine_payment'):
            return self.env['account.move.line']
        else:
            return super()._create_combine_account_payment(payment_method, amounts, diff_amount)

    # ------------------------------------------------------------
    # MAIN SPLIT LOGIC (replaces standard receivable lines)
    # ------------------------------------------------------------
    def _create_account_move_with_split_receivables(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None, lines=None):
        _logger.warning("=== _create_account_move_with_split_receivables called")

        # First, let the standard method create all non‑receivable lines
        original_data = super(
            PosSession,
            self.with_context(skip_combine_payment=True)
        )._create_account_move(
            balancing_account,
            amount_to_balance,
            bank_payment_method_diffs
        )
        if original_data is None:
            original_data = {}

        if not self.move_id:
            raise UserError(_("No account move created for the session."))

        # Expected total = sum of ALL payments (including pay_later) – matches popup
        orders = self._get_closed_orders()
        total_expected = 0.0
        for order in orders:
            for payment in order.payment_ids:
                total_expected += payment.amount
        _logger.warning("Total expected (all payments): %s", total_expected)

        # Remove any existing receivable lines (the combined ones from the standard move)
        receivable_account_type = self._get_receivable_account_type()
        restricted_receivable_account_type = self._get_restricted_receivable_account_type()
        unrestricted_receivable_account_type = self._get_neutral_receivable_account_type()
        netural_receivable_account_type = self._get_unrestricted_receivable_account_type()
        # ------------------------------------------------------------
        # SAFELY NEUTRALIZE RECEIVABLE LINES (DO NOT DELETE)
        # ------------------------------------------------------------
        receivable_lines = self.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type in [
                receivable_account_type,
                restricted_receivable_account_type,
                unrestricted_receivable_account_type,
                netural_receivable_account_type
            ] and l.debit > 0
        )

        if receivable_lines:
            _logger.warning(
                "Neutralizing %d receivable lines instead of deleting",
                len(receivable_lines)
            )
            receivable_lines.with_context(check_move_validity=False).write({
                'debit': 0.0,
                'credit': 0.0,
            })

        if not lines:
            raise UserError(_("Split accounting requires lines data – none provided."))

        # Build split breakdown from UI
        payment_breakdown = {}
        total_split = 0.0
        for pm_id, vals in lines.items():
            pm = self.env['pos.payment.method'].browse(int(pm_id))
            if not pm:
                continue
            breakdown = {}
            for type_key in ['restricted', 'unrestricted', 'neutral']:
                breakdown[type_key] = []
                for entry in vals.get(type_key, []):
                    amount = entry.get('amount', 0.0)
                    if not float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                        breakdown[type_key].append({
                            'amount': amount,
                            'ref': entry.get('ref', ''),
                            'bank_id': entry.get('bank', False) and int(entry['bank']) or False,
                        })
                        total_split += amount
            payment_breakdown[int(pm_id)] = breakdown

        _logger.warning("Total split amount: %s (expected: %s)", total_split, total_expected)

        # Validate exact match – no rounding adjustment
        diff = total_expected - total_split
        if not float_is_zero(diff, precision_rounding=self.currency_id.rounding):
            raise UserError(_(
                "Split slips total (%.2f %s) does not match expected total (%.2f %s).\n"
                "Difference: %.2f %s.\n\n"
                "Please correct your entries.",
                total_split, self.currency_id.symbol,
                total_expected, self.currency_id.symbol,
                abs(diff), self.currency_id.symbol
            ))

        # Create split receivable lines
        split_line_ids = []
        total_new_debit = 0.0
        for pm_id, breakdown in payment_breakdown.items():
            pm = self.env['pos.payment.method'].browse(pm_id)
            for type_key in ['restricted', 'unrestricted', 'neutral']:
                raise UserError(str(breakdown))

                for entry in breakdown.get(type_key, []):
                    amount = entry.get('amount', 0.0)
                    if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                        continue
                    ref = entry.get('ref', '')
                    bank_id = entry.get('bank_id', False)
                    if type_key == 'restricted':
                        account = self._get_restricted_receivable_account(pm)
                        label = self.company_id.restricted_category or _('Restricted')
                    elif type_key == 'unrestricted':
                        account = self._get_unrestricted_receivable_account(pm)
                        label = self.company_id.unrestricted_category or _('Unrestricted')
                    else:
                        account = self._get_neutral_receivable_account(pm)
                        label = _('Non Donation')
                    if not account:
                        raise UserError(_("No account defined for %s (%s)", pm.name, label))
                    name = f"{self.name} - {label} {pm.name} - {ref}".strip()
                    line = self.env['account.move.line'].with_context(
                        check_move_validity=False
                    ).create({
                        'move_id': self.move_id.id,
                        'name': name,
                        'account_id': account.id,
                        'debit': amount,
                        'credit': 0.0,
                        'partner_id': False,
                        'bank_journal_id': bank_id,
                    })
                    split_line_ids.append(line.id)
                    total_new_debit += amount

        original_data['_split_receivable_lines'] = split_line_ids
        self._create_split_difference_lines(bank_payment_method_diffs or {}, payment_breakdown)

        _logger.warning("Split accounting completed – created %d lines, total debit %.2f",
                        len(split_line_ids), total_new_debit)
        return original_data

    # ------------------------------------------------------------
    # RECONCILIATION (safe for missing keys)
    # ------------------------------------------------------------
    def _reconcile_account_move_lines(self, data):
        """Defensively ensure all required keys exist before calling super."""
        if data is None:
            data = {}
        required_keys = [
            'payment_method_to_receivable_lines',
            'split_cash_statement_lines',
            'combine_cash_statement_lines',
            'split_cash_receivable_lines',
            'combine_cash_receivable_lines',
            'stock_output_lines',
            'payment_to_receivable_lines',
        ]
        for key in required_keys:
            if key not in data or data[key] is None:
                data[key] = {}

        # Call original reconciliation
        super()._reconcile_account_move_lines(data)

        # Custom reconciliation for split receivable lines
        split_line_ids = data.get('_split_receivable_lines', [])
        if not split_line_ids:
            return data

        split_lines = self.env['account.move.line'].browse(split_line_ids).exists()
        statement_lines = self.statement_line_ids

        for line in split_lines:
            pm_id = self._extract_payment_method_id_from_line(line)
            matching = statement_lines.filtered(
                lambda sl: sl.payment_method_id.id == pm_id and
                float_compare(abs(sl.amount), line.debit, precision_rounding=self.currency_id.rounding) == 0
            )
            if matching:
                (matching[0] | line).reconcile()
            else:
                _logger.warning("No matching statement line for %s (%s)", line.name, line.debit)
        return data

    # ------------------------------------------------------------
    # CLOSING FLOW OVERRIDES (pass lines correctly)
    # ------------------------------------------------------------
    def _validate_session(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None, lines=None):
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        self.ensure_one()
        data = {}
        sudo = self.user_has_groups('point_of_sale.group_pos_user')

        if self.order_ids.filtered(lambda o: o.state != 'cancel') or self.sudo().statement_line_ids:
            self.cash_real_transaction = sum(self.sudo().statement_line_ids.mapped('amount'))
            if self.state == 'closed':
                raise UserError(_('This session is already closed.'))
            self._check_if_no_draft_orders()
            self._check_invoices_are_posted()
            cash_difference_before = self.cash_register_difference

            if self.update_stock_at_closing:
                self._create_picking_at_end_of_session()
                self._get_closed_orders().filtered(lambda o: not o.is_total_cost_computed)._compute_total_cost_at_session_closing(self.picking_ids.move_ids)

            _logger.warning("=== _validate_session: lines received = %s", str(lines))

            try:
                with self.env.cr.savepoint():
                    if lines and any(lines.values()):
                        data = self.with_company(self.company_id).with_context(
                            check_move_validity=False, skip_invoice_sync=True
                        )._create_account_move_with_split_receivables(
                            balancing_account, amount_to_balance, bank_payment_method_diffs, lines
                        )
                    else:
                        _logger.warning("No split lines – using standard accounting")
                        data = super()._create_account_move(balancing_account, amount_to_balance, bank_payment_method_diffs)
            except AccessError as e:
                if sudo:
                    if lines and any(lines.values()):
                        data = self.sudo().with_company(self.company_id).with_context(
                            check_move_validity=False, skip_invoice_sync=True
                        )._create_account_move_with_split_receivables(
                            balancing_account, amount_to_balance, bank_payment_method_diffs, lines
                        )
                    else:
                        data = super()._create_account_move(balancing_account, amount_to_balance, bank_payment_method_diffs)
                else:
                    raise e

            if data is None:
                data = {}
                _logger.warning("_create_account_move returned None – using empty dict")

            balance = sum(self.move_id.line_ids.mapped('balance'))
            try:
                with self.move_id._check_balanced({'records': self.move_id.sudo()}):
                    pass
            except UserError as e:
                self.env.cr.rollback()
                return self._close_session_action(balance)

            self.sudo()._post_statement_difference(cash_difference_before, False)

            if self.move_id.line_ids:
                for dummy, amount_data in data.get('sales', {}).items():
                    self.env['account.move.line'].browse(amount_data['move_line_id']).sudo().with_company(self.company_id).write({
                        'price_subtotal': abs(amount_data['amount_converted']),
                        'price_total': abs(amount_data['amount_converted']) + abs(amount_data['tax_amount']),
                    })
                self.env['pos.order'].search([('session_id', '=', self.id), ('state', '=', 'paid')]).write({'state': 'done'})
                reconciliation_data = self.sudo().with_company(self.company_id)._reconcile_account_move_lines(data)
                if reconciliation_data is not None:
                    data = reconciliation_data
            else:
                self.move_id.sudo().unlink()
        else:
            self.sudo()._post_statement_difference(self.cash_register_difference, False)

        self.write({'state': 'closed'})
        return True

    def action_pos_session_closing_control(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None, lines=None):
        _logger.warning("Lines in action_pos_session_closing_control: %s", str(lines))
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        for session in self:
            if any(order.state == 'draft' for order in session.order_ids):
                raise UserError(_("You cannot close the POS when orders are still in draft"))
            if session.state == 'closed':
                raise UserError(_('This session is already closed.'))
            session.write({'state': 'closing_control', 'stop_at': fields.Datetime.now()})
            if not session.config_id.cash_control:
                return session.action_pos_session_close(balancing_account, amount_to_balance, bank_payment_method_diffs, lines)
            if session.rescue:
                default_cash = self.payment_method_ids.filtered(lambda pm: pm.type == 'cash')[0]
                orders = self._get_closed_orders()
                total_cash = sum(orders.payment_ids.filtered(lambda p: p.payment_method_id == default_cash).mapped('amount')) + self.cash_register_balance_start
                session.cash_register_balance_end_real = total_cash
            return session.action_pos_session_validate(balancing_account, amount_to_balance, bank_payment_method_diffs, lines)

    def action_pos_session_validate(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None, lines=None):
        return self.action_pos_session_close(balancing_account, amount_to_balance, bank_payment_method_diffs, lines)

    def action_pos_session_close(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None, lines=None):
        return self._validate_session(balancing_account, amount_to_balance, bank_payment_method_diffs, lines)

    def close_session_from_ui(self, bank_payment_method_diff_pairs=None, lines=None):
        _logger.warning("=== close_session_from_ui: lines = %s", str(lines))
        bank_diffs = dict(bank_payment_method_diff_pairs or [])
        self.ensure_one()
        check = self._cannot_close_session(bank_diffs)
        if check:
            return check
        try:
            result = self.action_pos_session_closing_control(bank_payment_method_diffs=bank_diffs, lines=lines)
        except UserError as e:
            return {
                'successful': False,
                'message': e.args[0] if e.args else str(e),
                'redirect': False
            }
        if isinstance(result, dict):
            return result
        try:
            self.message_post(body="Point of Sale Session ended")
        except Exception as e:
            _logger.warning("Could not send closing message: %s", str(e))
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