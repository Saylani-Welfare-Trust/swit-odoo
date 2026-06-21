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

    @api.depends('transaction_ids', 'transaction_ids.amount', 'reconciled_ids', 'opening_balance')
    def _compute_totals(self):
        for record in self:
            debit = 0.0
            credit = 0.0
            for trans in record.transaction_ids:
                if trans.amount > 0:
                    debit += trans.amount
                else:
                    credit += abs(trans.amount)
            record.total_debit = debit
            record.total_credit = credit
            record.closing_balance = record.opening_balance + debit - credit

    def action_import_statement(self):
        """Open wizard for importing bank statement"""
        self.ensure_one()
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
        if self.state != 'draft':
            raise UserError(_('Only draft reconciliations can be processed.'))
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
        account_id = self.env.context.get('default_account_id')
        if not account_id:
            raise UserError(_('Please select an account for reconciliation.'))
        return {
            'name': _('Master Reconciliation'),
            'type': 'ir.actions.act_window',
            'res_model': 'reconcile.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_master_id': self.id,
                'default_account_id': account_id,
            }
        }

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
        self.state = 'completed'
        self.reconciled_by = self.env.user
        self.reconciliation_date = fields.Datetime.now()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bank.reconciliation.master',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def action_cancel_reconciliation(self):
        """Cancel the reconciliation process"""
        self.ensure_one()
        if self.state == 'completed':
            raise UserError(_('Cannot cancel a completed reconciliation.'))
        self.reconciled_ids.unlink()
        self.transaction_ids.write({
            'state': 'draft',
            'matched_move_id': False,
            'reconciled': False
        })
        self.state = 'draft'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bank.reconciliation.master',
            'res_id': self.id,
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

    def action_export_reconciliation_report(self):
        """Export reconciliation report"""
        self.ensure_one()
        # Placeholder for report export
        pass