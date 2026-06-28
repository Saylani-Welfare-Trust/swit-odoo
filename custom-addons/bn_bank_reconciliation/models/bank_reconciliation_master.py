from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class BankReconciliationMaster(models.Model):
    _name = 'bank.reconciliation.master'
    _description = 'Bank Reconciliation Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

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
    )
    posted_account_id = fields.Many2one(
        'account.account',
        string='Posted Account',
        required=True,
        domain="[('account_type', 'in', ['asset_cash', 'asset_current'])]"
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
        store=True
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
    
    # Journal Entry created from reconciliation
    move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
        copy=False
    )

    created_by = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.user
    )
    reconciled_by = fields.Many2one(
        'res.users',
        string='Reconciled By'
    )
    reconciliation_date = fields.Datetime(
        string='Reconciliation Date'
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
        currency_field='currency_id'
    )
    closing_balance = fields.Monetary(
        string='Closing Balance',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )

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
        """Open wizard for importing bank statement"""
        self.ensure_one()

        if self.account_id.id == self.posted_account_id.id:
            raise UserError(_('Bank Account and Posted Account cannot be the same. Please select different accounts.'))

        return {
            'name': _('Import Bank Statement'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.bank.statement.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_master_id': self.id,
            }
        }

    def action_process_matching(self):
        """Process automatic matching for all transactions"""
        self.ensure_one()
        if self.state != 'uploaded':
            raise UserError(_('Only uploaded reconciliations can be processed.'))
        
        if not self.transaction_ids:
            raise UserError(_('No transactions found to match.'))
            
        self.transaction_ids._auto_match_transactions()
        self.state = 'in_progress'
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bank.reconciliation.master',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def action_master_reconcile(self):
        """Master reconciliation function for bulk reconciliation"""
        self.ensure_one()
        if self.state == 'completed':
            raise UserError(_('This reconciliation is already completed.'))
        
        unmatched_no_account = self.transaction_ids.filtered(
            lambda t: t.state == 'unmatched' and not t.account_id
        )
        if unmatched_no_account:
            raise UserError(_(
                'Some unmatched transactions do not have an account selected. '
                'Please select accounts for all unmatched transactions first.'
            ))
        
        # Reconcile all matched transactions
        matched_transactions = self.transaction_ids.filtered(lambda t: t.state == 'matched')
        if not matched_transactions:
            raise UserError(_('No matched transactions found to reconcile.'))
            
        for transaction in matched_transactions:
            if transaction.account_id:
                transaction.action_accept_match()

    def action_validate_reconciliation(self):
        """Validate and complete the reconciliation"""
        self.ensure_one()
        if self.state == 'completed':
            raise UserError(_('This reconciliation is already completed.'))
        
        unreconciled = self.transaction_ids.filtered(
            lambda t: t.state in ['matched', 'unmatched']
        )
        if unreconciled:
            raise UserError(_(
                'Cannot complete reconciliation. There are %d transactions '
                'that have not been reconciled.' % len(unreconciled)
            ))
        
        # Create journal entry for reconciliation
        self._create_reconciliation_journal_entry()
        
        self.state = 'completed'
        self.reconciled_by = self.env.user
        self.reconciliation_date = fields.Datetime.now()

    def _create_reconciliation_journal_entry(self):
        """Create journal entry for reconciled transactions"""
        self.ensure_one()
        
        if not self.reconciled_ids:
            raise UserError(_('No reconciled transactions found to create journal entry.'))
        
        # Check if journal entry already exists
        if self.move_id:
            raise UserError(_('Journal entry already exists for this reconciliation.'))
        
        # Prepare journal entry lines
        move_lines = []
        
        # Group transactions by account (excluding bank account)
        account_totals = {}
        total_debit = 0.0
        total_credit = 0.0
        
        for reconciled in self.reconciled_ids:
            account_id = reconciled.account_id.id
            if account_id not in account_totals:
                account_totals[account_id] = {
                    'debit': 0.0,
                    'credit': 0.0,
                    'account': reconciled.account_id,
                    'partner_id': reconciled.partner_id.id if reconciled.partner_id else False
                }
            account_totals[account_id]['debit'] += reconciled.debit or 0.0
            account_totals[account_id]['credit'] += reconciled.credit or 0.0
            total_debit += reconciled.debit or 0.0
            total_credit += reconciled.credit or 0.0
        
        # Create move lines for each account (excluding bank account)
        for account_id, totals in account_totals.items():
            # Skip if the account is the bank account
            if account_id == self.account_id.id:
                continue
                
            if totals['debit'] > 0 or totals['credit'] > 0:
                move_lines.append((0, 0, {
                    'account_id': account_id,
                    'partner_id': totals['partner_id'],
                    'debit': totals['debit'],
                    'credit': totals['credit'],
                    'name': _('Reconciliation: %s') % self.name,
                }))
        
        # Add posted account line (single line with net amount)
        net_amount = total_debit - total_credit
        
        if net_amount > 0:
            # Net debit, so credit the posted account
            move_lines.append((0, 0, {
                'account_id': self.posted_account_id.id,
                'debit': 0.0,
                'credit': net_amount,
                'name': _('Posted Account: %s') % self.posted_account_id.name,
            }))
        elif net_amount < 0:
            # Net credit, so debit the posted account
            move_lines.append((0, 0, {
                'account_id': self.posted_account_id.id,
                'debit': abs(net_amount),
                'credit': 0.0,
                'name': _('Posted Account: %s') % self.posted_account_id.name,
            }))
        
        # Validate that we have at least 2 lines for a balanced entry
        if len(move_lines) < 2:
            raise UserError(_('Cannot create journal entry: Need at least two lines for a balanced entry.'))
        
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
            
            # Update reconciled records with move reference
            for reconciled in self.reconciled_ids:
                reconciled.matched_move_id = move.id
                reconciled.is_posted = True
                
        except Exception as e:
            raise UserError(_('Error creating journal entry: %s') % str(e))

    def action_cancel_reconciliation(self):
        """Cancel the reconciliation process"""
        self.ensure_one()
        if self.state == 'completed':
            raise UserError(_('Cannot cancel a completed reconciliation.'))
        
        # Cancel and delete the journal entry if exists
        if self.move_id:
            if self.move_id.state == 'posted':
                self.move_id.button_cancel()
            self.move_id.unlink()
            self.move_id = False
        
        self.reconciled_ids.unlink()
        self.transaction_ids.write({
            'state': 'draft',
            'matched_move_id': False,
            'reconciled': False,
            'reconciled_date': False,
            'reconciled_by': False
        })
        self.state = 'cancelled'

    def action_view_move(self):
        """Open the journal entry"""
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
        """Open view with all transactions"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bank.reconciliation.transaction',
            'view_mode': 'tree,form',
            'domain': [('master_id', '=', self.id)],
            'context': {'default_master_id': self.id}
        }

    def action_view_reconciled(self):
        """Open view with reconciled transactions"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bank.reconciliation.reconciled',
            'view_mode': 'tree,form',
            'domain': [('master_id', '=', self.id)],
            'context': {'default_master_id': self.id}
        }

    def unlink(self):
        """Prevent deletion of non-draft reconciliations"""
        for record in self:
            if record.state != 'draft':
                raise UserError(_('You can only delete draft reconciliations.'))
        return super(BankReconciliationMaster, self).unlink()