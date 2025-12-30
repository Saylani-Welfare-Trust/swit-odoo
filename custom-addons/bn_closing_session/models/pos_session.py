from odoo.exceptions import AccessError, ValidationError, UserError
from odoo.tools import float_is_zero
from odoo import models, fields, _

import logging


_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.session'


    def _compute_closing_details(self):
        """Compute restricted/unrestricted breakdown per payment method for the session."""
        self.ensure_one()
        orders = self._get_closed_orders()
        breakdown_dict = {}
        order_total = 0.0
        
        # for order in orders.filtered(lambda o: o.state == 'paid'):
        for order in orders.filtered(lambda o: o.state in ['cfo_approval', 'paid']):
            order_restricted_amount = 0.0
            order_unrestricted_amount = 0.0
            order_neutral_amount = 0.0
            for line in order.lines:
                restriction_type = self._is_restricted_product(line.product_id)
                if restriction_type == 1:
                    order_restricted_amount += line.price_subtotal_incl
                elif restriction_type == 2:
                    order_unrestricted_amount += line.price_subtotal_incl
                elif restriction_type == 0:
                    order_neutral_amount += line.price_subtotal_incl

            order_total = order_restricted_amount + order_unrestricted_amount + order_neutral_amount
            if order_total == 0:
                continue

            restricted_ratio = order_restricted_amount / order_total
            unrestricted_ratio = order_unrestricted_amount / order_total
            neutral_ratio      = order_neutral_amount      / order_total


            for payment in order.payment_ids:
                method_id = payment.payment_method_id.id
                if method_id not in breakdown_dict:
                    breakdown_dict[method_id] = {'restricted': 0.0, 'unrestricted': 0.0, 'neutral': 0.0}
                breakdown_dict[method_id]['restricted'] += payment.amount * restricted_ratio
                breakdown_dict[method_id]['unrestricted'] += payment.amount * unrestricted_ratio
                breakdown_dict[method_id]['neutral'] += payment.amount * neutral_ratio

        return breakdown_dict

    def _compute_payment_breakdown(self):
        """Compute restricted/unrestricted payment breakdown using pos.session.slip records."""
        self.ensure_one()
        breakdown_dict = {}

        # Fetch slips for this session
        slips = self.env['pos.session.slip'].search([
            ('session_id', '=', self.id)
        ])

        for slip in slips:
            method_id = slip.pos_payment_method_id.id

            # Initialize if not already present
            if method_id not in breakdown_dict:
                breakdown_dict[method_id] = {
                    'restricted': [],
                    'unrestricted': [],
                    'neutral': [],

                }

            # Determine restricted/unrestricted account names
            restricted = self._get_unrestricted_category()
            unrestricted = self._get_restricted_category()

            # Decide based on slip.type
            if slip.type == restricted:
                breakdown_dict[method_id]['restricted'].append({
                    'amount': slip.amount,
                    'ref': slip.slip_no,
                })
            elif slip.type == unrestricted:
                breakdown_dict[method_id]['unrestricted'].append({
                    'amount': slip.amount,
                    'ref': slip.slip_no,
                })
            else: 
                breakdown_dict[method_id]['neutral'].append({
                    'amount': slip.amount,
                    'ref': slip.slip_no,
                })

        return breakdown_dict

    def _is_restricted_product(self, product):
        """
        Return 1 for restricted, 2 for unrestricted, False for neither
        """
        if product.categ_id:
            category_name = product.categ_id.complete_name.lower()

            if self._get_unrestricted_category().lower() in category_name:
                return 2
            elif self._get_restricted_category().lower() in category_name :
                return 1
        return 0   # NEUTRAL


    def get_closing_control_data(self):
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("You don't have the access rights to get the point of sale closing control data."))
        self.ensure_one()

        orders = self._get_closed_orders()
        payments = orders.payment_ids.filtered(lambda p: p.payment_method_id.type != "pay_later")
        cash_payment_method_ids = self.payment_method_ids.filtered(lambda pm: pm.type == 'cash')
        default_cash_payment_method_id = cash_payment_method_ids[0] if cash_payment_method_ids else None
        total_default_cash_payment_amount = sum(
            payments.filtered(lambda p: p.payment_method_id == default_cash_payment_method_id).mapped('amount')
        ) if default_cash_payment_method_id else 0
        other_payment_method_ids = self.payment_method_ids - default_cash_payment_method_id if default_cash_payment_method_id else self.payment_method_ids

        cash_in_count = 0
        cash_out_count = 0
        cash_in_out_list = []
        last_session = self.search([('config_id', '=', self.config_id.id), ('id', '!=', self.id)], limit=1)

        for cash_move in self.sudo().statement_line_ids.sorted('create_date'):
            if cash_move.amount > 0:
                cash_in_count += 1
                name = f'Cash in {cash_in_count}'
            else:
                cash_out_count += 1
                name = f'Cash out {cash_out_count}'
            cash_in_out_list.append({
                'name': cash_move.payment_ref if cash_move.payment_ref else name,
                'amount': cash_move.amount
            })

        # 🔥 Use helper instead of field
        breakdown_dict = self._compute_closing_details()

        default_cash_details = None
        if default_cash_payment_method_id:
            default_cash_details = {
                'name': default_cash_payment_method_id.name,
                'amount': last_session.cash_register_balance_end_real
                        + total_default_cash_payment_amount
                        + sum(self.sudo().statement_line_ids.mapped('amount')),
                'opening': last_session.cash_register_balance_end_real,
                'payment_amount': total_default_cash_payment_amount,
                'moves': cash_in_out_list,
                'id': default_cash_payment_method_id.id,
                'breakdown': breakdown_dict.get(default_cash_payment_method_id.id, {'restricted': 0.0, 'unrestricted': 0.0})
            }

        other_payment_methods = []
        for pm in other_payment_method_ids:
            payments_pm = orders.payment_ids.filtered(lambda p: p.payment_method_id == pm)
            other_payment_methods.append({
                'name': pm.name,
                'amount': sum(payments_pm.mapped('amount')),
                'number': len(payments_pm),
                'id': pm.id,
                'type': pm.type,
                'breakdown': breakdown_dict.get(pm.id, {'restricted': 0.0, 'unrestricted': 0.0, 'neutral': 0.0})
            })

        return {
            'orders_details': {
                'quantity': len(orders),
                'amount': sum(orders.mapped('amount_total'))
            },
            'opening_notes': self.opening_notes,
            'default_cash_details': default_cash_details,
            'other_payment_methods': other_payment_methods,
            'is_manager': self.user_has_groups("point_of_sale.group_pos_manager"),
            'amount_authorized_diff': self.config_id.amount_authorized_diff if self.config_id.set_maximum_difference else None
        }

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
            cash_difference_before_statements = self.cash_register_difference
            
            if self.update_stock_at_closing:
                self._create_picking_at_end_of_session()
                self._get_closed_orders().filtered(lambda o: not o.is_total_cost_computed)._compute_total_cost_at_session_closing(self.picking_ids.move_ids)
            
            _logger.warning("Lines Receive from Component _validate_session: %s", str(lines))

            computed = self._compute_payment_breakdown()

            try:
                with self.env.cr.savepoint():
                    # data = self.with_company(self.company_id).with_context(check_move_validity=False, skip_invoice_sync=True)._create_account_move(balancing_account, amount_to_balance, bank_payment_method_diffs)
                    
                    if lines or computed:
                        # ========== CUSTOM ACCOUNTING REPLACEMENT ==========
                        # REPLACE the original line:
                        # data = self.with_company(self.company_id).with_context(check_move_validity=False, skip_invoice_sync=True)._create_account_move(balancing_account, amount_to_balance, bank_payment_method_diffs)
                        
                        # WITH our custom method:
                        data = self.with_company(self.company_id).with_context(
                            check_move_validity=False, 
                            skip_invoice_sync=True
                        )._create_account_move_with_split_receivables(
                            balancing_account, amount_to_balance, bank_payment_method_diffs, lines
                        )
                        # raise UserError(str("DATA: " + str(data)))
                        # ========== END CUSTOM REPLACEMENT ==========
                    else:
                        data = self.with_company(self.company_id).with_context(check_move_validity=False, skip_invoice_sync=True)._create_account_move(balancing_account, amount_to_balance, bank_payment_method_diffs)
            except AccessError as e:
                if sudo:
                    if lines or computed:
                        # ========== CUSTOM ACCOUNTING REPLACEMENT (sudo version) ==========
                        data = self.sudo().with_company(self.company_id).with_context(
                            check_move_validity=False, 
                            skip_invoice_sync=True
                        )._create_account_move_with_split_receivables(
                            balancing_account, amount_to_balance, bank_payment_method_diffs, lines
                        )
                        # ========== END CUSTOM REPLACEMENT ==========
                    else:
                        data = self.with_company(self.company_id).with_context(check_move_validity=False, skip_invoice_sync=True)._create_account_move(balancing_account, amount_to_balance, bank_payment_method_diffs)
                else:
                    raise e

            balance = sum(self.move_id.line_ids.mapped('balance'))
            # raise UserError(str(data))
            
            try:
                with self.move_id._check_balanced({'records': self.move_id.sudo()}):
                    pass
            except UserError:
                # Creating the account move is just part of a big database transaction
                # when closing a session. There are other database changes that will happen
                # before attempting to create the account move, such as, creating the picking
                # records.
                # We don't, however, want them to be committed when the account move creation
                # failed; therefore, we need to roll back this transaction before showing the
                # close session wizard.
                self.env.cr.rollback()
                return self._close_session_action(balance)

            self.sudo()._post_statement_difference(cash_difference_before_statements, False)
            
            if self.move_id.line_ids:
                # self.move_id.sudo().with_company(self.company_id)._post()
                
                # We need to write the price_subtotal and price_total here because if we do it earlier 
                # the compute functions will overwrite it here /account/models/account_move_line.py _compute_totals
                for dummy, amount_data in data['sales'].items():
                    self.env['account.move.line'].browse(amount_data['move_line_id']).sudo().with_company(self.company_id).write({
                        'price_subtotal': abs(amount_data['amount_converted']),
                        'price_total': abs(amount_data['amount_converted']) + abs(amount_data['tax_amount']),
                    })
                
                # Set the uninvoiced orders' state to 'done'
                self.env['pos.order'].search([('session_id', '=', self.id), ('state', '=', 'paid')]).write({'state': 'done'})
            else:
                self.move_id.sudo().unlink()
            
            self.sudo().with_company(self.company_id)._reconcile_account_move_lines(data)
        else:
            self.sudo()._post_statement_difference(self.cash_register_difference, False)

        self.write({'state': 'closed'})
        return True

    

    def _find_payment_method_for_receivable_line(self, line):
        """Find which payment method a receivable line belongs to."""
        if not line.name:
            return None
        # raise UserError(str("LINE NAME: " + str(line.name) + " PAYMENT METHODS: " + str(self.payment_method_ids.read())))
        line_name_lower = line.name.lower()
        
        # Check each payment method for name matching
        for payment_method in self.payment_method_ids:
            method_name_lower = payment_method.name.lower() if payment_method.name else ""
            
            # Direct matching: if payment method name appears in line name
            if method_name_lower and method_name_lower in line_name_lower:
                return payment_method
        
        # Final fallback: return first available method
        if self.payment_method_ids:
            return self.payment_method_ids[0]
            
        return None
       
    def _create_account_move_with_split_receivables(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None, lines=None):
        _logger.warning("Lines Receive from Component _create_account_move_with_split_receivables: %s", str(lines))
        
        original_data = super(PosSession, self)._create_account_move(
            balancing_account, amount_to_balance, bank_payment_method_diffs
        )

        # raise ValidationError(str(lines))

        account_move = self.move_id

        # raise ValidationError(str(account_move.read()))

        payment_breakdown = {}

        # 🔥 Decide source of breakdown
        if lines:
            # Keep frontend format (don’t aggregate)
            payment_breakdown = {int(pm_id): vals for pm_id, vals in lines.items()}
        else:
            # backend fallback: computed already returns the desired lists
            computed = self._compute_payment_breakdown()
            payment_breakdown = {int(pm_id): {'restricted': vals.get('restricted', []) or [], 'unrestricted': vals.get('unrestricted', []) or [], 'neutral': vals.get('neutral', []) or []} for pm_id, vals in computed.items()}

        # raise ValidationError(str(payment_breakdown))
        # raise ValidationError(account_move.line_ids.mapped("account_id.name"))
        receivable_lines = account_move.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable' and l.debit > 0
            # lambda l: l.account_id.account_type == 'asset_current' and l.debit > 0
        )

        # raise ValidationError(
        #     f"""
        # Receivable Lines: {receivable_lines}
        # Breakdown: {payment_breakdown}
        # Payment Methods IDs: {self.payment_method_ids.ids}
        # Payment Methods Names: {self.payment_method_ids.mapped('name')}
        # """
        # )
        payment_method_amounts = self._group_receivable_lines_by_payment_method(receivable_lines)
        receivable_lines.unlink()

        split_data = self._create_split_receivable_lines(account_move, payment_method_amounts, payment_breakdown)
        self._create_split_difference_lines(account_move, bank_payment_method_diffs, payment_breakdown)

        for key in list(original_data.keys()):
            if 'combine_receivables' in key or 'payment_method_to_receivable_lines' in key:
                if hasattr(original_data[key], 'ids'):
                    original_data[key] = self.env['account.move.line']
                else:
                    original_data[key] = {}

        original_data['_split_data'] = split_data

        # raise ValidationError(str(original_data))
        
        return original_data

    def _group_receivable_lines_by_payment_method(self, receivable_lines):
        """Group receivable lines by their corresponding payment method."""
        payment_method_amounts = {}
        # raise ValidationError(str("RECEIVABLE LINES: " + str(receivable_lines)))
        for line in receivable_lines:
            payment_method = self._find_payment_method_for_receivable_line(line)
            # raise UserError(str("LINE: " + str(line.name) + " METHOD: " + str(payment_method.name if payment_method else "None")))
            
            if payment_method:
                if payment_method.id not in payment_method_amounts:
                    payment_method_amounts[payment_method.id] = {
                        'total_amount': 0.0,
                        'method': payment_method,
                        'lines': []
                    }
                payment_method_amounts[payment_method.id]['total_amount'] += abs(line.balance)
                payment_method_amounts[payment_method.id]['lines'].append(line)
        
        return payment_method_amounts
           
    def _create_split_receivable_lines(self, account_move, payment_method_amounts, payment_breakdown):
        """Create restricted and unrestricted receivable lines with per-entry slip references."""
        split_data = {
            'restricted_lines': [],
            'unrestricted_lines': [],
            'neutral_lines': [],
            'move_id': account_move.id
        }

        # Debug: raise before account selection
        # raise ValidationError("Product split debug:\n" + str(payment_method_amounts) + "\n----\n" + str(payment_breakdown))

        for pm_id, pm_data in payment_method_amounts.items():
            payment_method = pm_data['method']
            breakdown = payment_breakdown.get(pm_id, {})

            # Restricted entries
            for entry in breakdown.get("restricted", []):
                amount = entry.get("amount", 0.0)
                if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    continue
                ref = entry.get("ref") or ""
                restricted_account = self._get_restricted_receivable_account(payment_method)
                line = self._create_receivable_line(
                    account_move,
                    restricted_account,
                    amount,
                    f"{self.name} - Restricted {payment_method.name} - {ref}".strip()
                )
                split_data['restricted_lines'].append({
                    'move_line_id': line.id,
                    'amount': amount,
                    'payment_method_id': payment_method.id,
                    'account_id': restricted_account.id,
                    'payment_method_name': payment_method.name,
                    'ref': ref,
                })

            # Unrestricted entries
            for entry in breakdown.get("unrestricted", []):
                amount = entry.get("amount", 0.0)
                if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    continue
                ref = entry.get("ref") or ""
                unrestricted_account = self._get_unrestricted_receivable_account(payment_method)
                line = self._create_receivable_line(
                    account_move,
                    unrestricted_account,
                    amount,
                    f"{self.name} - Unrestricted {payment_method.name} - {ref}".strip()
                )
                split_data['unrestricted_lines'].append({
                    'move_line_id': line.id,
                    'amount': amount,
                    'payment_method_id': payment_method.id,
                    'account_id': unrestricted_account.id,
                    'payment_method_name': payment_method.name,
                    'ref': ref,
                })
            # Neutral entries
            for entry in breakdown.get("neutral", []):
                amount = entry.get("amount", 0.0)
                if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    continue
                ref = entry.get("ref") or ""
                neutral_account = self._get_neutral_receivable_account(payment_method)
                line = self._create_receivable_line(
                    account_move,
                    neutral_account,
                    amount,
                    f"{self.name} - Neutral {payment_method.name} - {ref}".strip()
                )
                split_data['neutral_lines'].append({
                    'move_line_id': line.id,
                    'amount': amount,
                    'payment_method_id': payment_method.id,
                    'account_id': neutral_account.id,
                    'payment_method_name': payment_method.name,
                    'ref': ref,
                })
        return split_data

    def _create_receivable_line(self, account_move, account, amount, name):
        """Helper to create a receivable journal item."""
        return self.env['account.move.line'].create({
            'move_id': account_move.id,
            'name': name,
            'account_id': account.id,
            'debit': amount,
            'credit': 0.0,
            'partner_id': False,
        })

    def _create_split_difference_lines(self, account_move, bank_payment_method_diffs, payment_breakdown):
        """Create split difference lines for bank payment methods (per entry, like receivable splits)."""
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        
        for pm_id, diff in bank_payment_method_diffs.items():
            if float_is_zero(diff, precision_rounding=self.currency_id.rounding):
                continue

            payment_method = self.env['pos.payment.method'].browse(pm_id)
            if not payment_method:
                continue

            breakdown = payment_breakdown.get(pm_id, {})

            # Restricted difference entries
            for entry in breakdown.get("restricted", []):
                amount = entry.get("amount", 0.0)
                if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    continue
                self._create_receivable_line(
                    account_move,
                    self._get_restricted_receivable_account(payment_method),
                    abs(amount),
                    f"Difference - Restricted {payment_method.name}"
                )

            # Unrestricted difference entries
            for entry in breakdown.get("unrestricted", []):
                amount = entry.get("amount", 0.0)
                if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    continue
                self._create_receivable_line(
                    account_move,
                    self._get_unrestricted_receivable_account(payment_method),
                    abs(amount),
                    f"Difference - Unrestricted {payment_method.name}"
                )
            # Neutral difference
            for entry in breakdown.get("neutral", []):
                amount = entry.get("amount", 0.0)
                if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    continue
                self._create_receivable_line(
                    account_move,
                    self._get_neutral_receivable_account(payment_method),
                    abs(amount),
                    f"Difference - Neutral {payment_method.name}"
                )


    def _reconcile_account_move_lines(self, data):
        """Handle reconciliation for both original and split accounting."""
        
        # First, remove the COMBINED receivable lines since we're using SPLIT ones
        split_data = data.get('_split_data', {})
        if split_data:
            # Remove combined cash receivable lines to avoid duplication
            combined_lines_to_remove = []
            for key, lines in data.items():
                if 'combine_receivables' in key and lines:
                    if isinstance(lines, dict):
                        for pm, line_data in lines.items():
                            if 'move_line_id' in line_data:
                                combined_lines_to_remove.append(line_data['move_line_id'])
                    elif hasattr(lines, 'ids'):
                        combined_lines_to_remove.extend(lines.ids)
            
            # Remove the combined receivable lines
            if combined_lines_to_remove:
                combined_lines = self.env['account.move.line'].browse(combined_lines_to_remove)
                combined_lines.unlink()
        
        # Then let original method handle the rest
        try:
            data = super(PosSession, self)._reconcile_account_move_lines(data)
        except Exception as e:
            _logger.warning("Original reconciliation failed: %s", str(e))
        
        # Now handle our split receivable reconciliation
        if '_split_data' in data:
            self._reconcile_split_receivable_lines(data['_split_data'])
        
        return data

    def _reconcile_split_receivable_lines(self, split_data):
        """Reconcile split receivable lines with statement lines."""
        try:
            # Get all statement lines
            statement_lines = self.statement_line_ids
            
            # Reconcile restricted lines
            for line_data in split_data.get('restricted_lines', []):
                self._reconcile_single_line(line_data, statement_lines)
            
            # Reconcile unrestricted lines  
            for line_data in split_data.get('unrestricted_lines', []):
                self._reconcile_single_line(line_data, statement_lines)
            
            # Reconcile neutral lines
            for line_data in split_data.get('neutral_lines', []):
                self._reconcile_single_line(line_data, statement_lines)
                
        except Exception as e:
            _logger.error("Error in split receivable reconciliation: %s", str(e))

    def _reconcile_single_line(self, line_data, statement_lines):
        """Reconcile a single split line with statement lines."""
        payment_method_id = line_data.get('payment_method_id')
        amount = line_data['amount']
        move_line = self.env['account.move.line'].browse(line_data['move_line_id'])
        
        # Find matching statement line by payment method AND amount
        matching_st_lines = statement_lines.filtered(
            lambda sl: sl.payment_method_id.id == payment_method_id and 
                    float_is_zero(abs(sl.amount) - amount, precision_rounding=self.currency_id.rounding)
        )
        
        if matching_st_lines:
            (matching_st_lines[0] | move_line).reconcile()

    def _get_restricted_category(self):
        """Returns the default Restricted Category if no restricted category is set on the payment method."""
        return self.company_id.restricted_category
    
    def _get_unrestricted_category(self):
        """Returns the default Unrestricted Category if no unrestricted category is set on the payment method."""
        return self.company_id.unrestricted_category

    def _get_restricted_receivable_account(self, payment_method):
        """Returns the default pos receivable account if no receivable_account_id is set on the payment method."""
        return payment_method.restricted_account_id or self.company_id.account_default_pos_restricted_receivable_account_id
    
    def _get_neutral_receivable_account(self, payment_method):
        return payment_method.receivable_account_id or self.company_id.account_default_pos_receivable_account_id

    
    def _get_unrestricted_receivable_account(self, payment_method):
        """Returns the default pos receivable account if no receivable_account_id is set on the payment method."""
        return payment_method.unrestricted_account_id or self.company_id.account_default_pos_unrestricted_receivable_account_id

    def action_pos_session_closing_control(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None, lines=None):
        _logger.warning("Lines Receive from Component action_pos_session_closing_control: %s", str(lines))

        bank_payment_method_diffs = bank_payment_method_diffs or {}
        for session in self:
            if any(order.state == 'draft' for order in session.order_ids):
                raise UserError(_("You cannot close the POS when orders are still in draft"))
            if session.state == 'closed':
                raise UserError(_('This session is already closed.'))
            stop_at = self.stop_at or fields.Datetime.now()
            session.write({'state': 'closing_control', 'stop_at': stop_at})
            if not session.config_id.cash_control:
                return session.action_pos_session_close(balancing_account, amount_to_balance, bank_payment_method_diffs, lines)
            # If the session is in rescue, we only compute the payments in the cash register
            # It is not yet possible to close a rescue session through the front end, see `close_session_from_ui`
            if session.rescue and session.config_id.cash_control:
                default_cash_payment_method_id = self.payment_method_ids.filtered(lambda pm: pm.type == 'cash')[0]
                orders = self._get_closed_orders()
                total_cash = sum(
                    orders.payment_ids.filtered(lambda p: p.payment_method_id == default_cash_payment_method_id).mapped('amount')
                ) + self.cash_register_balance_start

                session.cash_register_balance_end_real = total_cash

            return session.action_pos_session_validate(balancing_account, amount_to_balance, bank_payment_method_diffs, lines)

    def action_pos_session_validate(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None, lines=None):
        _logger.warning("Lines Receive from Component action_pos_session_validate: %s", str(lines))

        bank_payment_method_diffs = bank_payment_method_diffs or {}
        return self.action_pos_session_close(balancing_account, amount_to_balance, bank_payment_method_diffs, lines)

    def action_pos_session_close(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None, lines=None):
        _logger.warning("Lines Receive from Component action_pos_session_close: %s", str(lines))

        bank_payment_method_diffs = bank_payment_method_diffs or {}
        # Session without cash payment method will not have a cash register.
        # However, there could be other payment methods, thus, session still
        # needs to be validated.
        return self._validate_session(balancing_account, amount_to_balance, bank_payment_method_diffs, lines)

    def close_session_from_ui(self, bank_payment_method_diff_pairs=None, lines=None):
        """Extended: Also receive restricted/unrestricted payment lines.

        param bank_payment_method_diff_pairs: list[(int, float)]
            Pairs of payment_method_id and diff_amount which will be used to post
            loss/profit when closing the session.

        param lines: dict[int, dict[str, list[dict]]]
            Example:
            {
                5: { "restricted": [{"id": 1, "amount": 200.0, "ref": "slip-001"}],
                    "unrestricted": [{"id": 2, "amount": 300.0, "ref": "slip-002"}]
                },
                7: { "restricted": [], "unrestricted": [{"id": 3, "amount": 500.0}] }
            }
        """

        _logger.warning("Lines Receive from Component close_session_from_ui: %s", str(lines))

        bank_payment_method_diffs = dict(bank_payment_method_diff_pairs or [])
        self.ensure_one()

        # 🔹 Keep default logic intact
        check_closing_session = self._cannot_close_session(bank_payment_method_diffs)
        if check_closing_session:
            return check_closing_session

        # raise UserError(str(lines))

        validate_result = self.action_pos_session_closing_control(
            bank_payment_method_diffs=bank_payment_method_diffs,
            lines=lines
        )

        if isinstance(validate_result, dict):
            return {
                "successful": False,
                "message": validate_result.get("name"),
                "redirect": True,
            }

        self.message_post(body="Point of Sale Session ended")

        return {"successful": True}
    
    def _loader_params_res_company(self):
        # OVERRIDE to load the fields in pos data (load_pos_data)
        vals = super()._loader_params_res_company()
        vals['search_params']['fields'] += ['restricted_category', 'unrestricted_category']
        
        return vals
    
    def show_session_slip(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Deposit Slip',
            'res_model': 'pos.session.slip',
            'domain': [('session_id', '=', self.id)],
            'view_mode': 'tree'
        }