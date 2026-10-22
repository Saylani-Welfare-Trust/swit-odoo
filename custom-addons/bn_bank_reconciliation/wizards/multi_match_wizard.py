from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


class ReconcileMultiMatchWizard(models.TransientModel):
    """Reconcile several bank statement lines with one journal entry: a new
    entry for lines with no entry in Odoo (e.g. bank charges), or an existing
    entry the lines add up to (e.g. a deposit the bank shows in several lines)."""
    _name = 'reconcile.multi.match.wizard'
    _description = 'Match Several Statement Lines with One Entry'

    master_id = fields.Many2one(
        'bank.reconciliation.master',
        string='Reconciliation',
        required=True
    )
    currency_id = fields.Many2one(
        related='master_id.currency_id'
    )
    transaction_ids = fields.Many2many(
        'bank.reconciliation.transaction',
        'reconcile_multi_match_transaction_rel',
        'wizard_id',
        'transaction_id',
        string='Statement Lines',
        domain="[('master_id', '=', master_id), ('state', '!=', 'reconciled')]"
    )
    match_mode = fields.Selection([
        ('create', 'Create a new entry'),
        ('existing', 'Match an existing entry'),
    ], string='Entry', default='create', required=True)
    statement_total = fields.Monetary(
        string='Statement Lines Total',
        compute='_compute_totals',
        currency_field='currency_id'
    )

    # New entry
    account_id = fields.Many2one(
        'account.account',
        string='Account',
        domain="[('deprecated', '=', False), ('company_id', '=', company_id)]",
        help='Account of the new entry, e.g. Bank Charges. The other side is the Posted Account.'
    )
    company_id = fields.Many2one(
        related='master_id.company_id'
    )
    label = fields.Char(
        string='Label',
        help='Reference of the new entry, e.g. "Bank charges October"'
    )
    date = fields.Date(
        string='Entry Date',
        compute='_compute_date',
        store=True,
        readonly=False
    )
    entry_preview = fields.Text(
        string='Entry Preview',
        compute='_compute_entry_preview'
    )

    # Existing entry
    show_only_matching_amount = fields.Boolean(
        string='Only Matching Amount',
        default=True,
        help='Only offer the entries whose amount equals the total of the selected statement lines'
    )
    available_line_ids = fields.Many2many(
        'account.move.line',
        compute='_compute_available_line_ids'
    )
    move_line_id = fields.Many2one(
        'account.move.line',
        string='Journal Entry',
        domain="[('id', 'in', available_line_ids)]"
    )
    entry_amount = fields.Monetary(
        string='Entry Amount',
        compute='_compute_totals',
        currency_field='currency_id'
    )
    difference = fields.Monetary(
        string='Difference',
        compute='_compute_totals',
        currency_field='currency_id'
    )

    @api.depends('transaction_ids', 'move_line_id')
    def _compute_totals(self):
        for wizard in self:
            wizard.statement_total = sum(abs(transaction.amount) for transaction in wizard.transaction_ids)
            wizard.entry_amount = abs(wizard.move_line_id.balance)
            wizard.difference = wizard.statement_total - wizard.entry_amount

    @api.depends('transaction_ids', 'master_id')
    def _compute_date(self):
        for wizard in self:
            dates = wizard.transaction_ids.mapped('date')
            wizard.date = max(dates) if dates else wizard.master_id.date

    @api.depends('master_id', 'transaction_ids', 'show_only_matching_amount')
    def _compute_available_line_ids(self):
        for wizard in self:
            if not wizard.master_id:
                wizard.available_line_ids = False
                continue
            # Entries waiting on the selected lines themselves are offered too
            lines = self.env['account.move.line'].search(
                wizard.master_id._get_candidate_move_line_domain(wizard.transaction_ids._origin)
            )
            if wizard.show_only_matching_amount and wizard.transaction_ids:
                tolerance = wizard.master_id.match_tolerance_amount or 0.01
                lines = lines.filtered(
                    lambda line: abs(abs(line.balance) - wizard.statement_total) <= tolerance
                )
            wizard.available_line_ids = lines

    @api.depends('match_mode', 'transaction_ids', 'account_id', 'master_id')
    def _compute_entry_preview(self):
        for wizard in self:
            if wizard.match_mode != 'create' or not wizard.transaction_ids or not wizard.account_id:
                wizard.entry_preview = False
                continue
            if wizard._has_both_sides():
                wizard.entry_preview = _('The selected statement lines must be on the same side (all debit or all credit).')
                continue
            total = formatLang(self.env, wizard.statement_total, currency_obj=wizard.currency_id)
            account = wizard.account_id.display_name
            bank = wizard.master_id.posted_account_id.display_name
            if wizard._is_money_out():
                debit, credit = account, bank
            else:
                debit, credit = bank, account
            wizard.entry_preview = _('Debit  %(debit)s  %(total)s\nCredit  %(credit)s  %(total)s') % {
                'debit': debit, 'credit': credit, 'total': total,
            }

    def _has_both_sides(self):
        return bool(self.transaction_ids.filtered(lambda t: t.amount > 0)) and \
            bool(self.transaction_ids.filtered(lambda t: t.amount < 0))

    def _is_money_out(self):
        # A Debit on the bank statement is money taken out of the account
        return self.transaction_ids[:1].amount > 0

    def action_match(self):
        self.ensure_one()
        transactions = self.transaction_ids
        if not transactions:
            raise UserError(_('Please select the statement lines to match.'))

        reconciled = transactions.filtered(lambda t: t.state == 'reconciled')
        if reconciled:
            raise UserError(_(
                'These statement lines are already reconciled: %s'
            ) % ', '.join(reconciled.mapped('description')))

        # One entry is either money in or money out
        if self._has_both_sides():
            raise UserError(_(
                'All the selected statement lines must be on the same side (all debit or all credit).'
            ))

        if self.match_mode == 'create':
            line = self._create_entry()
            account = self.account_id
        else:
            line = self._check_existing_entry()
            account = False

        match = {
            'move_line': line,
            'move': line.move_id,
        }
        for transaction in transactions:
            transaction._apply_match(match, manual=True)
            if account:
                # The statement line shows the account it was booked to, not the bank
                transaction.account_id = account
        for transaction in transactions:
            transaction.action_accept_match()

        if self.master_id.state == 'uploaded':
            self.master_id.state = 'in_progress'
        return {'type': 'ir.actions.act_window_close'}

    def _create_entry(self):
        """Book the statement lines on the selected account against the Posted
        Account, and return the Posted Account item. The entry stays in draft:
        Validate & Complete posts it with the other matched entries."""
        self.ensure_one()
        master = self.master_id
        bank_account = master.posted_account_id
        if not self.account_id:
            raise UserError(_('Please select the account of the new entry, e.g. Bank Charges.'))
        if self.account_id == bank_account:
            raise UserError(_('The account must be different from the Posted Account (%s).') % bank_account.display_name)

        money_out = self._is_money_out()
        line_vals = []
        for transaction in self.transaction_ids:
            amount = master.currency_id.round(abs(transaction.amount))
            line_vals.append((0, 0, {
                'account_id': self.account_id.id,
                'partner_id': transaction.partner_id.id,
                'name': transaction.description,
                'debit': amount if money_out else 0.0,
                'credit': 0.0 if money_out else amount,
            }))
        total = master.currency_id.round(self.statement_total)
        line_vals.append((0, 0, {
            'account_id': bank_account.id,
            'name': self.label or _('Bank statement lines'),
            'debit': 0.0 if money_out else total,
            'credit': total if money_out else 0.0,
        }))

        move = self.env['account.move'].create({
            'journal_id': master.journal_id.id,
            'date': self.date or master.date,
            'ref': self.label or master.name,
            'company_id': master.company_id.id,
            'narration': _('Bank Reconciliation: %s') % master.name,
            'bank_reconciliation_created_id': master.id,
            'line_ids': line_vals,
        })
        return move.line_ids.filtered(lambda line: line.account_id == bank_account)

    def _check_existing_entry(self):
        self.ensure_one()
        line = self.move_line_id
        if not line:
            raise UserError(_('Please select the journal entry.'))

        tolerance = self.master_id.match_tolerance_amount or 0.01
        if abs(self.difference) > tolerance:
            raise UserError(_(
                'The selected statement lines total %s but the entry is %s.'
            ) % (self.statement_total, self.entry_amount))

        # The entry may have been matched with another statement line meanwhile
        domain = self.master_id._get_candidate_move_line_domain(self.transaction_ids)
        if not self.env['account.move.line'].search_count(domain + [('id', '=', line.id)]):
            raise UserError(_(
                'The entry %s is no longer available for matching.'
            ) % line.move_id.display_name)
        return line
