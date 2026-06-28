from odoo import fields, models, api, _
from odoo.exceptions import UserError


class BankReconciliationReconciled(models.Model):
    _name = 'bank.reconciliation.reconciled'
    _description = 'Bank Reconciliation Reconciled Transaction'
    _order = 'reconciliation_date desc, id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    master_id = fields.Many2one(
        'bank.reconciliation.master',
        string='Reconciliation Master',
        required=True,
        ondelete='cascade'
    )
    transaction_id = fields.Many2one(
        'bank.reconciliation.transaction',
        string='Original Transaction',
        required=True,
        ondelete='cascade'
    )
    company_id = fields.Many2one(
        'res.company',
        related='master_id.company_id',
        string='Company',
        store=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='master_id.currency_id',
        string='Currency'
    )

    date = fields.Date(
        string='Transaction Date',
        required=True
    )
    description = fields.Text(
        string='Description',
        required=True
    )
    
    # Debit and Credit fields
    debit = fields.Monetary(
        string='Debit',
        currency_field='currency_id',
        help='Debit amount for this transaction'
    )
    credit = fields.Monetary(
        string='Credit',
        currency_field='currency_id',
        help='Credit amount for this transaction'
    )
    amount = fields.Monetary(
        string='Net Amount',
        compute='_compute_amount',
        store=True,
        currency_field='currency_id',
        help='Net amount (Debit - Credit)'
    )
    
    reference = fields.Char(
        string='Reference'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner'
    )

    account_id = fields.Many2one(
        'account.account',
        string='Account',
        required=True
    )
    matched_move_id = fields.Many2one(
        'account.move',
        string='Reconciled Entry'
    )
    matched_move_line_id = fields.Many2one(
        'account.move.line',
        string='Reconciled Journal Item'
    )
    confidence_level = fields.Selection([
        ('high', 'High Match'),
        ('medium', 'Medium Match'),
        ('low', 'Low Match')
    ], string='Confidence Level')

    reconciled_by = fields.Many2one(
        'res.users',
        string='Reconciled By',
        required=True,
        default=lambda self: self.env.user
    )
    reconciliation_date = fields.Datetime(
        string='Reconciliation Date',
        required=True,
        default=fields.Datetime.now
    )

    notes = fields.Text(string='Notes')
    adjustment_type = fields.Selection([
        ('bank_charge', 'Bank Charge'),
        ('withholding_tax', 'Withholding Tax'),
        ('interest_income', 'Interest Income'),
        ('miscellaneous', 'Miscellaneous Expense'),
        ('transfer', 'Bank Transfer')
    ], string='Adjustment Type')
    
    # Flag to indicate if this reconciled record has been posted
    is_posted = fields.Boolean(
        string='Is Posted',
        default=False,
        help='Indicates if this reconciled transaction has been posted to accounting'
    )
    
    # Journal entry line reference
    journal_line_id = fields.Many2one(
        'account.move.line',
        string='Journal Entry Line',
        help='The journal entry line created for this reconciled transaction'
    )

    _sql_constraints = [
        ('unique_reconciled_transaction', 'unique(transaction_id)',
         'This transaction is already reconciled.')
    ]

    @api.depends('debit', 'credit')
    def _compute_amount(self):
        """Compute net amount from debit and credit"""
        for record in self:
            record.amount = (record.debit or 0.0) - (record.credit or 0.0)

    def action_view_move(self):
        """View the accounting entry for this reconciled transaction"""
        self.ensure_one()
        if not self.matched_move_id:
            raise UserError(_('No accounting entry found for this reconciliation.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.matched_move_id.id,
            'view_mode': 'form',
            'target': 'current'
        }
    
    def action_view_journal_line(self):
        """View the specific journal line for this reconciled transaction"""
        self.ensure_one()
        if not self.journal_line_id:
            raise UserError(_('No journal line found for this reconciled transaction.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'res_id': self.journal_line_id.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def action_unreconcile(self):
        """Unreconcile this transaction"""
        self.ensure_one()
        
        # Check if reconciliation is completed
        if self.master_id.state == 'completed':
            raise UserError(_('Cannot unreconcile from a completed reconciliation.'))
        
        # If there's a journal entry, remove reference
        if self.journal_line_id:
            # Don't delete the line, just remove reference
            self.journal_line_id = False        
        # Update the original transaction
        if self.transaction_id:
            self.transaction_id.write({
                'state': 'matched',
                'reconciled': False,
                'reconciled_date': False,
                'reconciled_by': False
            })
        
        # Delete the reconciled record
        self.unlink()
        return True

    @api.model
    def create(self, vals):
        """Ensure debit and credit are properly set on creation"""
        # If amount is provided but debit/credit not, set appropriate defaults
        if 'amount' in vals and 'debit' not in vals and 'credit' not in vals:
            if vals['amount'] >= 0:
                vals['debit'] = vals['amount']
                vals['credit'] = 0.0
            else:
                vals['debit'] = 0.0
                vals['credit'] = abs(vals['amount'])
        
        # Create the record
        record = super(BankReconciliationReconciled, self).create(vals)
        
        # If the master is in completed state, this record is already posted
        if record.master_id and record.master_id.state == 'completed':
            record.is_posted = True
        
        return record

    def write(self, vals):
        """Handle writing of debit/credit fields and state updates"""
        # If amount is provided but debit/credit not, set appropriate defaults
        if 'amount' in vals and 'debit' not in vals and 'credit' not in vals:
            if vals['amount'] >= 0:
                vals['debit'] = vals['amount']
                vals['credit'] = 0.0
            else:
                vals['debit'] = 0.0
                vals['credit'] = abs(vals['amount'])
        
        return super(BankReconciliationReconciled, self).write(vals)