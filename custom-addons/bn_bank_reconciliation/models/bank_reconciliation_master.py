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
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        required=True,
        domain="[('type', 'in', ['bank', 'cash'])]"
    )
    posted_account_id = fields.Many2one(
        related='journal_id.default_account_id',
        string='Posted Account',
        required=True,
        store=True,
        domain="[('account_type', 'in', ['asset_cash', 'asset_current']), ('deprecated', '=', False)]"
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
    bank_statement_config_id = fields.Many2one(
        'bank.statement.config',
        string='Bank Statement Config',
        required=True
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
    unreconciled_transaction_ids = fields.One2many(
        'bank.reconciliation.transaction',
        'master_id',
        string='Unreconciled Transactions',
        compute='_compute_unreconciled_transactions'
    )
    matched_transaction_ids = fields.One2many(
        'bank.reconciliation.transaction',
        'master_id',
        string='Matched and Reconciled Transactions',
        compute='_compute_unreconciled_transactions'
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

    @api.constrains('date')
    def _check_date(self):
        for record in self:
            if record.date and record.date > fields.Date.context_today(record):
                raise ValidationError(_('Statement Date cannot be in the future.'))

    file = fields.Binary(string='File', attachment=True)
    file_name = fields.Char(string='File Name')
    # file_type = fields.Selection([
    #     ('csv', 'CSV'),
    #     ('xls', 'Excel (.xls)'),
    #     ('xlsx', 'Excel (.xlsx)'),
    # ], string='File Type', compute='_compute_file_type', store=False)
    delimiter = fields.Selection([
        (',', 'Comma (,)'),
        (';', 'Semicolon (;)'),
        ('\t', 'Tab'),
    ], string='CSV Delimiter', default=',')


    # @api.depends('file_name')
    # def _compute_file_type(self):
    #     for rec in self:
    #         if rec.file_name:
    #             ext = rec.file_name.lower().split('.')[-1]
    #             if ext in ('csv',):
    #                 rec.file_type = 'csv'
    #             elif ext in ('xls',):
    #                 rec.file_type = 'xls'
    #             elif ext in ('xlsx',):
    #                 rec.file_type = 'xlsx'
    #             else:
    #                 rec.file_type = False
    #         else:
    #             rec.file_type = False

    @api.onchange('bank_statement_config_id')
    def _onchange_bank_statement_config_id(self):
        # The journal can only be changed on a draft reconciliation
        if self.state == 'draft' and self.bank_statement_config_id.journal_id:
            self.journal_id = self.bank_statement_config_id.journal_id

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('bank.reconciliation.master') or _('New')
        return super(BankReconciliationMaster, self).create(vals)

    @api.depends('transaction_ids', 'transaction_ids.state', 'reconciled_ids', 'reconciled_ids.active')
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

    @api.depends(
        'transaction_ids',
        'transaction_ids.state',
        'reconciled_ids',
        'reconciled_ids.transaction_id'
    )
    def _compute_unreconciled_transactions(self):
        # Lines with a match (ready to accept) or already reconciled go to the
        # Reconciled tab; the Unreconciled tab keeps the lines with no match
        for record in self:
            reconciled_transactions = record.reconciled_ids.mapped('transaction_id')
            matched = record.transaction_ids.filtered(
                lambda transaction: (
                    transaction.state in ['matched', 'reconciled']
                    or transaction in reconciled_transactions
                )
            )
            record.matched_transaction_ids = matched
            record.unreconciled_transaction_ids = record.transaction_ids - matched

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

    def _get_candidate_move_line_domain(self, transaction=None):
        """Journal items a statement line can be compared with: the items of the
        selected journal's posted entries, whatever their account, that are not
        bank reconciled yet. A statement line is reconciled with whole entries, so an
        entry is offered only once. Income, expense, receivable and payable items are
        left out: the bank movement is the other side of the entry (bank,
        settlement...). Money in on the statement (Credit) is a debit on that side,
        money out (Debit) a credit."""
        self.ensure_one()
        journal = self.journal_id
        # Entries waiting on another statement line's match are not available
        matched_domain = [
            ('state', '=', 'matched'),
            ('matched_move_line_id', '!=', False),
            ('master_id.journal_id', '=', journal.id),
        ]
        if transaction:
            matched_domain.append(('id', 'not in', transaction.ids))
        matched_moves = self.env['bank.reconciliation.transaction'].search(
            matched_domain
        ).mapped('matched_move_line_id.move_id')
        domain = [
            ('journal_id', '=', journal.id),
            ('account_id.internal_group', 'not in', ['income', 'expense']),
            ('account_id.account_type', 'not in', ['asset_receivable', 'liability_payable']),
            ('parent_state', '=', 'posted'),
            ('is_bank_reconciled', '=', False),
            ('reconciled', '=', False),
            ('company_id', '=', self.company_id.id),
            ('move_id', 'not in', matched_moves.ids),
        ]
        if transaction:
            money_in = transaction.filtered(lambda t: t.credit > t.debit)
            if money_in == transaction:
                domain.append(('balance', '>', 0))
            elif not money_in:
                domain.append(('balance', '<', 0))
        return domain

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
        
        reconciled_transactions = self.reconciled_ids.mapped('transaction_id')
        to_match = self.transaction_ids.filtered(
            lambda t: t.state in ['draft', 'unmatched'] and t not in reconciled_transactions
        )
        if not to_match:
            raise UserError(_('No transactions were processed for matching.'))

        # Entries of the same day first, so that a line does not take another day's
        # entry of the same amount that the line of that day needs; then the entries
        # within the date tolerance
        to_match.with_context(bank_rec_same_day=True)._auto_match_transactions()
        to_match.filtered(lambda t: t.state == 'unmatched')._auto_match_transactions()

        self.state = 'in_progress'

    def action_master_reconcile(self):
        self.ensure_one()
        if not self.env.user.has_group('bn_bank_reconciliation.bank_reconciliation_master_reconcile_group'):
            raise UserError(_('You are not allowed to use Master Reconcile.'))
        if self.state == 'completed':
            raise UserError(_('This reconciliation is already completed.'))
        if self.state == 'cancelled':
            raise UserError(_('This reconciliation is cancelled.'))
        
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

    def action_open_multi_match(self):
        self.ensure_one()
        if self.state not in ['uploaded', 'in_progress']:
            raise UserError(_('Statement lines can only be matched while the reconciliation is uploaded or in progress.'))
        return {
            'name': _('Match Several Statement Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'reconcile.multi.match.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_master_id': self.id},
        }

    def action_validate_reconciliation(self):
        self.ensure_one()
        if self.state == 'completed':
            raise UserError(_('This reconciliation is already completed.'))
        if self.state == 'cancelled':
            raise UserError(_('This reconciliation is cancelled.'))
        
        # The matched entries that are still in draft are posted on completion,
        # so that they reach their accounts
        matched_moves = self.reconciled_ids.mapped('matched_move_id') | self.env['account.move.line'].search([
            ('bank_reconciliation_transaction_id', 'in', self.transaction_ids.ids)
        ]).mapped('move_id')
        matched_moves.filtered(lambda move: move.state == 'draft').action_post()

        not_posted = self.reconciled_ids.filtered(lambda r: r.matched_move_id.state != 'posted')
        if not_posted:
            raise UserError(_(
                'Some reconciled transactions are matched with an entry that is cancelled or deleted.\n'
                'Please unreconcile them first.\n'
                'Transactions: %s'
            ) % ', '.join(not_posted.mapped('description')))
        self.reconciled_ids.write({'is_posted': True})

        # Each reconciled line has its own reconciliation entry, created on Accept;
        # lines accepted before the entries were made on Accept get theirs now
        self.reconciled_ids._check_bank_side()
        self.reconciled_ids._create_reconciliation_move()
        self.reconciled_ids.mapped('reconciliation_move_id').filtered(
            lambda move: move.state == 'draft'
        ).action_post()
        
        self.write({
            'state': 'completed',
            'reconciled_by': self.env.user.id,
            'reconciliation_date': fields.Datetime.now(),
        })

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
        
        # Reconciled records are never deleted: archive them to keep the history
        self.reconciled_ids.write({'active': False})
        self.transaction_ids._release_move_lines()
        # Entries created for statement lines with no entry in Odoo are not needed any more
        self.env['account.move'].search([
            ('bank_reconciliation_created_id', '=', self.id),
            ('state', '=', 'draft'),
        ]).button_cancel()
        
        self.transaction_ids.write({
            'state': 'draft',
            'matched_move_id': False,
            'matched_move_line_id': False,
            'reconciled': False,
            'reconciled_date': False,
            'reconciled_by': False,
        })
        
        self.state = 'cancelled'

    def action_view_matched_moves(self):
        self.ensure_one()
        matched_moves = self.reconciled_ids.mapped('matched_move_id').exists()
        if not matched_moves:
            raise UserError(_('No matched journal entries found for this reconciliation.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'name': _('Matched Journal Entries'),
            'view_mode': 'tree,form',
            'domain': [('id', 'in', matched_moves.ids)],
            'target': 'current',
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
        raise UserError(_('You cannot delete a bank reconciliation.'))
        # for record in self:
        #     if record.state != 'draft':
        #         raise UserError(_('You can only delete draft reconciliations.'))
        #     if record.transaction_ids:
        #         raise UserError(_('Cannot delete a reconciliation with transactions. Please cancel it first.'))
        # return super(BankReconciliationMaster, self).unlink()