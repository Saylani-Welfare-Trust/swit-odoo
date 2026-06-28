from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class BankReconciliationMaster(models.Model):
    _name = 'bank.reconciliation.master'
    _description = 'Bank Reconciliation Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    date = fields.Date(
        string='Statement Date',
        required=True,
        default=fields.Date.context_today
    )
    account_id = fields.Many2one(
        'account.account',
        string='Bank Account',
        required=True,
        domain="[('deprecated', '=', False)]"
    )
    posted_account_id = fields.Many2one(
        'account.account',
        string='Posted Account',
        required=True,
        domain="[('account_type', 'in', ['asset_cash', 'asset_current']), ('deprecated', '=', False)]"
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        required=True,
        domain="[('type', 'in', ['bank', 'cash'])]"
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('uploaded', 'Uploaded'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    total_transactions = fields.Integer(
        string='Total Transactions',
        compute='_compute_transaction_counts',
        store=True
    )
    matched_transactions = fields.Integer(
        string='Matched Transactions',
        compute='_compute_transaction_counts',
        store=True
    )
    unmatched_transactions = fields.Integer(
        string='Unmatched Transactions',
        compute='_compute_transaction_counts',
        store=True
    )
    reconciled_transactions = fields.Integer(
        string='Reconciled Transactions',
        compute='_compute_transaction_counts',
        store=True
    )
    pending_transactions = fields.Integer(
        string='Pending Transactions',
        compute='_compute_transaction_counts',
        store=True
    )
    reconciliation_percentage = fields.Float(
        string='Reconciliation Percentage',
        compute='_compute_transaction_counts',
        store=True,
        digits=(5, 2)
    )

    transaction_ids = fields.One2many(
        'bank.reconciliation.transaction',
        'master_id',
        string='Transactions'
    )
    reconciled_ids = fields.One2many(
        'bank.reconciliation.reconciled',
        'master_id',
        string='Reconciled Transactions'
    )
    
    move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
        copy=False
    )

    created_by = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.user,
        readonly=True
    )
    reconciled_by = fields.Many2one(
        'res.users',
        string='Reconciled By',
        readonly=True
    )
    reconciliation_date = fields.Datetime(
        string='Reconciliation Date',
        readonly=True
    )

    note = fields.Text(string='Notes')
    
    total_debit = fields.Monetary(
        string='Total Debit',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )
    total_credit = fields.Monetary(
        string='Total Credit',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )
    total_amount = fields.Monetary(
        string='Total Amount',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )
    opening_balance = fields.Monetary(
        string='Opening Balance',
        currency_field='currency_id',
        default=0.0
    )
    closing_balance = fields.Monetary(
        string='Closing Balance',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )
    
    matching_algorithm = fields.Selection([
        ('exact', 'Exact Match'),
        ('fuzzy', 'Fuzzy Match'),
        ('intelligent', 'Intelligent Match')
    ], string='Matching Algorithm', default='intelligent')
    
    match_by_amount = fields.Boolean(string='Match by Amount', default=True)
    match_by_reference = fields.Boolean(string='Match by Reference', default=True)
    match_by_partner = fields.Boolean(string='Match by Partner', default=True)
    match_by_invoice = fields.Boolean(string='Match by Invoice', default=True)
    match_by_date = fields.Boolean(string='Match by Date', default=False)
    match_tolerance_days = fields.Integer(string='Date Tolerance (Days)', default=3)
    match_tolerance_amount = fields.Float(string='Amount Tolerance', default=0.01)

    @api.constrains('account_id', 'posted_account_id')
    def _check_accounts(self):
        for record in self:
            if record.account_id and record.posted_account_id:
                if record.account_id.id == record.posted_account_id.id:
                    raise ValidationError(_('Bank Account and Posted Account cannot be the same.'))

    @api.constrains('date')
    def _check_date(self):
        for record in self:
            if record.date and record.date > fields.Date.context_today(record):
                raise ValidationError(_('Statement Date cannot be in the future.'))

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('bank.reconciliation.master') or _('New')
        return super(BankReconciliationMaster, self).create(vals)

    @api.depends('transaction_ids', 'transaction_ids.state', 'reconciled_ids')
    def _compute_transaction_counts(self):
        for record in self:
            total = len(record.transaction_ids)
            matched = len(record.transaction_ids.filtered(lambda t: t.state == 'matched'))
            unmatched = len(record.transaction_ids.filtered(lambda t: t.state == 'unmatched'))
            reconciled = len(record.reconciled_ids)
            pending = len(record.transaction_ids.filtered(lambda t: t.state in ['matched', 'unmatched']))
            record.total_transactions = total
            record.matched_transactions = matched
            record.unmatched_transactions = unmatched
            record.reconciled_transactions = reconciled
            record.pending_transactions = pending
            record.reconciliation_percentage = (reconciled / total * 100) if total > 0 else 0.0

    @api.depends('transaction_ids', 'transaction_ids.debit', 'transaction_ids.credit', 'reconciled_ids', 'opening_balance')
    def _compute_totals(self):
        for record in self:
            total_debit = 0.0
            total_credit = 0.0
            total_amount = 0.0
            
            for trans in record.transaction_ids:
                total_debit += trans.debit or 0.0
                total_credit += trans.credit or 0.0
                total_amount += trans.amount or 0.0
                
            record.total_debit = total_debit
            record.total_credit = total_credit
            record.total_amount = total_amount
            record.closing_balance = record.opening_balance + total_debit - total_credit

    def action_import_statement(self):
        self.ensure_one()
        if self.state not in ['draft', 'uploaded']:
            raise UserError(_('You can only import statements in Draft or Uploaded state.'))
        
        return {
            'name': _('Import Bank Statement'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.bank.statement.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_master_id': self.id},
        }

    def action_process_matching(self):
        self.ensure_one()
        if self.state != 'uploaded':
            raise UserError(_('Only uploaded reconciliations can be processed.'))
        if not self.transaction_ids:
            raise UserError(_('No transactions found to match.'))
        
        processed = 0
        for transaction in self.transaction_ids:
            # Skip if already reconciled
            if transaction.state == 'reconciled':
                continue
            # Skip if already has reconciled record
            if self.env['bank.reconciliation.reconciled'].search_count([('transaction_id', '=', transaction.id)]) > 0:
                continue
            if transaction.state in ['draft', 'unmatched']:
                transaction._auto_match_transactions()
                processed += 1
        
        if processed == 0:
            raise UserError(_('No transactions were processed for matching.'))
        
        self.state = 'in_progress'

    def action_master_reconcile(self):
        self.ensure_one()
        if self.state == 'completed':
            raise UserError(_('This reconciliation is already completed.'))
        if self.state == 'cancelled':
            raise UserError(_('This reconciliation is cancelled.'))
        
        unmatched_no_account = self.transaction_ids.filtered(
            lambda t: t.state == 'unmatched' and not t.account_id
        )
        if unmatched_no_account:
            raise UserError(_(
                'Some unmatched transactions do not have an account selected. '
                'Please select accounts for all unmatched transactions first.\n'
                'Transactions: %s' % ', '.join(unmatched_no_account.mapped('description'))
            ))
        
        matched_transactions = self.transaction_ids.filtered(lambda t: t.state == 'matched')
        if not matched_transactions:
            raise UserError(_('No matched transactions found to reconcile.'))
        
        reconciled_count = 0
        for transaction in matched_transactions:
            # Skip if already reconciled
            if transaction.state == 'reconciled':
                continue
            # Skip if already has reconciled record
            if self.env['bank.reconciliation.reconciled'].search_count([('transaction_id', '=', transaction.id)]) > 0:
                continue
            if transaction.account_id:
                try:
                    transaction.action_accept_match()
                    reconciled_count += 1
                except Exception as e:
                    _logger.error("Failed to reconcile transaction %s: %s", transaction.id, str(e))
                    raise UserError(_('Failed to reconcile transaction %s: %s') % (transaction.description, str(e)))
        
        if reconciled_count == 0:
            raise UserError(_('No transactions were reconciled.'))
        
        self.state = 'in_progress'

    def action_validate_reconciliation(self):
        self.ensure_one()
        if self.state == 'completed':
            raise UserError(_('This reconciliation is already completed.'))
        if self.state == 'cancelled':
            raise UserError(_('This reconciliation is cancelled.'))
        
        unreconciled = self.transaction_ids.filtered(
            lambda t: t.state in ['matched', 'unmatched']
        )
        if unreconciled:
            raise UserError(_(
                'Cannot complete reconciliation. There are %d transactions '
                'that have not been reconciled.\n'
                'Please reconcile or reject them first.'
            ) % len(unreconciled))
        
        not_posted = self.reconciled_ids.filtered(lambda r: not r.is_posted)
        if not_posted:
            raise UserError(_(
                'Some reconciled transactions are not posted to accounting.\n'
                'Please post them first or enable auto-posting.'
            ))
        
        self._create_reconciliation_journal_entry()
        
        self.write({
            'state': 'completed',
            'reconciled_by': self.env.user.id,
            'reconciliation_date': fields.Datetime.now(),
        })

    def _create_reconciliation_journal_entry(self):
        self.ensure_one()
        if not self.reconciled_ids:
            raise UserError(_('No reconciled transactions found to create journal entry.'))
        if self.move_id:
            raise UserError(_('Journal entry already exists for this reconciliation.'))
        
        move_lines = []
        account_totals = {}
        total_debit = 0.0
        total_credit = 0.0
        
        for reconciled in self.reconciled_ids:
            if not reconciled.account_id:
                continue
            account_id = reconciled.account_id.id
            if account_id not in account_totals:
                account_totals[account_id] = {
                    'debit': 0.0,
                    'credit': 0.0,
                    'account': reconciled.account_id,
                    'partner_id': reconciled.partner_id.id if reconciled.partner_id else False,
                }
            account_totals[account_id]['debit'] += reconciled.debit or 0.0
            account_totals[account_id]['credit'] += reconciled.credit or 0.0
            total_debit += reconciled.debit or 0.0
            total_credit += reconciled.credit or 0.0
        
        if total_debit == 0 and total_credit == 0:
            raise UserError(_('Total debit and credit are zero. No journal entry needed.'))
        
        for account_id, totals in account_totals.items():
            if totals['debit'] == 0 and totals['credit'] == 0:
                continue
            move_lines.append((0, 0, {
                'account_id': account_id,
                'partner_id': totals['partner_id'],
                'debit': totals['debit'],
                'credit': totals['credit'],
                'name': _('Reconciliation: %s') % self.name,
                'is_bank_reconciled': True,
                'bank_reconciliation_id': self.id,
                'bank_reconciliation_date': self.date,
            }))
        
        net_amount = total_debit - total_credit
        if net_amount > 0:
            move_lines.append((0, 0, {
                'account_id': self.posted_account_id.id,
                'debit': 0.0,
                'credit': net_amount,
                'name': _('Contra - %s') % self.posted_account_id.name,
                'is_bank_reconciled': True,
                'bank_reconciliation_id': self.id,
                'bank_reconciliation_date': self.date,
            }))
        elif net_amount < 0:
            move_lines.append((0, 0, {
                'account_id': self.posted_account_id.id,
                'debit': abs(net_amount),
                'credit': 0.0,
                'name': _('Contra - %s') % self.posted_account_id.name,
                'is_bank_reconciled': True,
                'bank_reconciliation_id': self.id,
                'bank_reconciliation_date': self.date,
            }))
        
        if len(move_lines) < 2:
            raise UserError(_('Cannot create journal entry: Need at least two lines for a balanced entry.'))
        
        total_debit_lines = sum(line[2]['debit'] for line in move_lines)
        total_credit_lines = sum(line[2]['credit'] for line in move_lines)
        if abs(total_debit_lines - total_credit_lines) > 0.01:
            raise UserError(_(
                'Journal entry is not balanced. Debit: %s, Credit: %s'
            ) % (total_debit_lines, total_credit_lines))
        
        try:
            move = self.env['account.move'].create({
                'journal_id': self.journal_id.id,
                'date': self.date or fields.Date.today(),
                'ref': self.name,
                'company_id': self.company_id.id,
                'line_ids': move_lines,
                'narration': _('Bank Reconciliation: %s') % self.name,
                'state': 'draft',
            })
            move.action_post()
            self.move_id = move.id
            
            for reconciled in self.reconciled_ids:
                reconciled.write({
                    'matched_move_id': move.id,
                    'is_posted': True,
                })
                for line in move.line_ids:
                    if line.account_id.id == reconciled.account_id.id:
                        reconciled.journal_line_id = line.id
                        break
                        
        except Exception as e:
            raise UserError(_('Error creating journal entry: %s') % str(e))

    def action_cancel_reconciliation(self):
        self.ensure_one()
        if self.state == 'completed':
            raise UserError(_('Cannot cancel a completed reconciliation.'))
        
        if self.move_id:
            try:
                if self.move_id.state == 'posted':
                    self.move_id.button_cancel()
                self.move_id.unlink()
                self.move_id = False
            except Exception as e:
                raise UserError(_('Error removing journal entry: %s') % str(e))
        
        self.reconciled_ids.unlink()
        
        self.transaction_ids.write({
            'state': 'draft',
            'matched_move_id': False,
            'matched_move_line_id': False,
            'reconciled': False,
            'reconciled_date': False,
            'reconciled_by': False,
        })
        
        self.state = 'cancelled'

    def action_view_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_('No journal entry found for this reconciliation.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def action_view_transactions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bank.reconciliation.transaction',
            'view_mode': 'tree,form',
            'domain': [('master_id', '=', self.id)],
            'context': {'default_master_id': self.id}
        }

    def action_view_reconciled(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bank.reconciliation.reconciled',
            'view_mode': 'tree,form',
            'domain': [('master_id', '=', self.id)],
            'context': {'default_master_id': self.id}
        }

    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_('You can only delete draft reconciliations.'))
            if record.transaction_ids:
                raise UserError(_('Cannot delete a reconciliation with transactions. Please cancel it first.'))
        return super(BankReconciliationMaster, self).unlink()