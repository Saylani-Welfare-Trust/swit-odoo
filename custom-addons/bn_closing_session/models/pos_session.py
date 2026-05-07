from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare, float_is_zero
from odoo import models, fields, _, api
import logging

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.session'

    # ------------------------------------------------------------
    # DATA COMPUTATION FOR THE CLOSING POPUP
    # ------------------------------------------------------------
    def _compute_closing_details(self):
        """Compute restricted/unrestricted/neutral breakdown per payment method."""
        self.ensure_one()
        orders = self._get_closed_orders()
        breakdown = {}
        for order in orders.filtered(lambda o: o.state in ['refund', 'paid']):
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

    def _compute_payment_breakdown(self):
        """Read stored slips for the session."""
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
        """Return 1=restricted, 2=unrestricted, 0=neutral based on category name."""
        if not product.categ_id:
            return 0
        cat_name = product.categ_id.complete_name.lower()
        if self.company_id.unrestricted_category.lower() in cat_name:
            return 2
        if self.company_id.restricted_category.lower() in cat_name:
            return 1
        return 0

    def _get_closed_orders(self):
        return self.order_ids.filtered(lambda o: o.state in ['refund', 'paid', 'done'])

    def get_closing_control_data(self):
        """Data for the closing popup (called from JS)."""
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
                'amount': last_session.cash_register_balance_end_real + total_cash + sum(cash_moves.mapped('amount')),
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
    # OVERRIDES FOR CLOSING WITH SPLIT ACCOUNTING
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

            _logger.warning("Lines received in _validate_session: %s", str(lines))

            try:
                with self.env.cr.savepoint():
                    if lines:
                        data = self.with_company(self.company_id).with_context(
                            check_move_validity=False, skip_invoice_sync=True
                        )._create_account_move_with_split_receivables(
                            balancing_account, amount_to_balance, bank_payment_method_diffs, lines
                        )
                    else:
                        data = self.with_company(self.company_id).with_context(
                            check_move_validity=False, skip_invoice_sync=True
                        )._create_account_move(balancing_account, amount_to_balance, bank_payment_method_diffs)
            except AccessError as e:
                if sudo:
                    if lines:
                        data = self.sudo().with_company(self.company_id).with_context(
                            check_move_validity=False, skip_invoice_sync=True
                        )._create_account_move_with_split_receivables(
                            balancing_account, amount_to_balance, bank_payment_method_diffs, lines
                        )
                    else:
                        data = self.with_company(self.company_id).with_context(
                            check_move_validity=False, skip_invoice_sync=True
                        )._create_account_move(balancing_account, amount_to_balance, bank_payment_method_diffs)
                else:
                    raise e

            # Verify balance
            try:
                with self.move_id._check_balanced({'records': self.move_id.sudo()}):
                    pass
            except UserError:
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
            else:
                self.move_id.sudo().unlink()

            self.sudo().with_company(self.company_id)._reconcile_account_move_lines(data)
        else:
            self.sudo()._post_statement_difference(self.cash_register_difference, False)

        self.write({'state': 'closed'})
        return True

    def _create_account_move_with_split_receivables(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None, lines=None):
        """Create account move but replace combined receivable lines with split ones."""
        # First let super do its work (creates move and usual lines)
        original_data = super()._create_account_move(balancing_account, amount_to_balance, bank_payment_method_diffs)

        # Remove the combined receivable lines that were just created
        receivable_lines = self.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable' and l.debit > 0
        )
        receivable_lines.unlink()

        # Use provided lines or fallback to computed slips
        if lines:
            payment_breakdown = {}
            for pm_id, vals in lines.items():
                pm = self.env['pos.payment.method'].browse(int(pm_id))
                breakdown = {}
                for type_key in ['restricted', 'unrestricted', 'neutral']:
                    breakdown[type_key] = []
                    for entry in vals.get(type_key, []):
                        if entry.get('amount', 0.0):
                            breakdown[type_key].append({
                                'amount': entry['amount'],
                                'ref': entry.get('ref', ''),
                                'bank_id': entry.get('bank', False) and int(entry['bank']) or False,
                            })
                payment_breakdown[int(pm_id)] = breakdown
        else:
            payment_breakdown = self._compute_payment_breakdown()

        # Create split receivable lines
        split_line_ids = self._create_split_receivable_lines(payment_breakdown)

        # Attach split line ids to the returned data so reconciliation can use them
        original_data['_split_receivable_lines'] = split_line_ids

        # Also handle bank differences if any
        self._create_split_difference_lines(bank_payment_method_diffs or {}, payment_breakdown)

        return original_data

    def _create_split_receivable_lines(self, payment_breakdown):
        """Create one receivable line per (payment method, restriction type, slip)."""
        created_ids = []
        for pm_id, breakdown in payment_breakdown.items():
            pm = self.env['pos.payment.method'].browse(pm_id)
            for type_key in ['restricted', 'unrestricted', 'neutral']:
                for entry in breakdown.get(type_key, []):
                    amount = entry.get('amount', 0.0)
                    if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                        continue
                    ref = entry.get('ref', '')
                    bank_id = entry.get('bank_id', False)
                    # Choose account based on type
                    if type_key == 'restricted':
                        account = self._get_restricted_receivable_account(pm)
                        label = f"{self._get_restricted_category()}"
                    elif type_key == 'unrestricted':
                        account = self._get_unrestricted_receivable_account(pm)
                        label = f"{self._get_unrestricted_category()}"
                    else:
                        account = self._get_neutral_receivable_account(pm)
                        label = "Non Donation"
                    name = f"{self.name} - {label} {pm.name} - {ref}".strip()
                    line = self.env['account.move.line'].create({
                        'move_id': self.move_id.id,
                        'name': name,
                        'account_id': account.id,
                        'debit': amount,
                        'credit': 0.0,
                        'partner_id': False,
                        'bank_journal_id': bank_id,
                    })
                    created_ids.append(line.id)
        return created_ids

    def _create_split_difference_lines(self, bank_payment_method_diffs, payment_breakdown):
        """Create difference (loss/profit) lines per split category if needed."""
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        for pm_id, diff in bank_payment_method_diffs.items():
            if float_is_zero(diff, precision_rounding=self.currency_id.rounding):
                continue
            pm = self.env['pos.payment.method'].browse(pm_id)
            # For simplicity, we apply the whole diff to the neutral account.
            # Adapt as needed for your business logic.
            account = self._get_neutral_receivable_account(pm)
            self.env['account.move.line'].create({
                'move_id': self.move_id.id,
                'name': f"Diff - {pm.name} - Bank difference",
                'account_id': account.id,
                'debit': diff if diff > 0 else 0,
                'credit': -diff if diff < 0 else 0,
                'partner_id': False,
            })

    def _reconcile_account_move_lines(self, data):
        """Reconcile the split receivable lines with statement lines."""
        # Reconcile the normal lines (taxes, sales) using parent method
        try:
            super()._reconcile_account_move_lines(data)
        except Exception as e:
            _logger.warning("Original reconciliation failed: %s", str(e))

        # Now reconcile our split receivable lines
        split_line_ids = data.get('_split_receivable_lines', [])
        if not split_line_ids:
            return

        split_lines = self.env['account.move.line'].browse(split_line_ids)
        statement_lines = self.statement_line_ids

        for line in split_lines:
            # Match statement line by bank journal and amount
            matching = statement_lines.filtered(
                lambda sl: sl.payment_method_id.id == self._extract_payment_method_id_from_line(line) and
                           float_compare(abs(sl.amount), line.debit, precision_rounding=self.currency_id.rounding) == 0
            )
            if matching:
                (matching[0] | line).reconcile()

    def _extract_payment_method_id_from_line(self, line):
        """Helper to guess payment method id from line name (falls back to first bank method)."""
        name = line.name or ''
        for pm in self.payment_method_ids.filtered(lambda p: p.type == 'bank'):
            if pm.name in name:
                return pm.id
        return self.payment_method_ids.filtered(lambda p: p.type == 'bank')[:1].id

    # ------------------------------------------------------------
    # HELPERS FOR ACCOUNTS AND CATEGORIES
    # ------------------------------------------------------------
    def _get_restricted_category(self):
        return self.company_id.restricted_category

    def _get_unrestricted_category(self):
        return self.company_id.unrestricted_category

    def _get_restricted_receivable_account(self, payment_method):
        return payment_method.restricted_account_id or self.company_id.account_default_pos_restricted_receivable_account_id

    def _get_neutral_receivable_account(self, payment_method):
        return payment_method.neutral_account_id or self.company_id.account_default_pos_neutral_receivable_account_id

    def _get_unrestricted_receivable_account(self, payment_method):
        return payment_method.unrestricted_account_id or self.company_id.account_default_pos_unrestricted_receivable_account_id

    # ------------------------------------------------------------
    # OVERRIDES FOR CLOSING FLOW
    # ------------------------------------------------------------
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
        """Entry point from the JS popup."""
        _logger.warning("Lines in close_session_from_ui: %s", str(lines))
        bank_diffs = dict(bank_payment_method_diff_pairs or [])
        self.ensure_one()
        check = self._cannot_close_session(bank_diffs)
        if check:
            return check
        result = self.action_pos_session_closing_control(bank_payment_method_diffs=bank_diffs, lines=lines)
        if isinstance(result, dict):
            return {"successful": False, "message": result.get("name"), "redirect": True}
        self.message_post(body="Point of Sale Session ended")
        return {"successful": True}

    # ------------------------------------------------------------
    # EXTRA METHODS FOR COMPANY FIELDS LOADING
    # ------------------------------------------------------------
    def _loader_params_res_company(self):
        vals = super()._loader_params_res_company()
        vals['search_params']['fields'] += ['restricted_category', 'unrestricted_category']
        return vals

    def action_show_payments_list(self):
        return {
            'name': _('Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'pos.payment',
            'view_mode': 'tree,form',
            'domain': [('session_id', '=', self.id)],
            'context': {'search_default_group_by_payment_method': 1},
        }

    @api.depends('order_ids.payment_ids.amount')
    def _compute_total_payments_amount(self):
        result = self.env['pos.payment']._read_group([('session_id', 'in', self.ids)], ['session_id'], ['amount:sum'])
        mapping = {r['session_id'][0]: r['amount'] for r in result}
        for session in self:
            session.total_payments_amount = mapping.get(session.id, 0.0)

    def show_session_slip(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Deposit Slip',
            'res_model': 'pos.session.slip',
            'domain': [('session_id', '=', self.id)],
            'view_mode': 'tree',
        }