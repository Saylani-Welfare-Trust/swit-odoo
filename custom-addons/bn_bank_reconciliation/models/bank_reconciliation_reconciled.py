from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class BankReconciliationReconciled(models.Model):
    _name = 'bank.reconciliation.reconciled'
    _description = 'Bank Reconciliation Reconciled Transaction'
    _order = 'reconciliation_date desc, id'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'description'

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
    
    debit = fields.Monetary(
        string='Debit',
        currency_field='currency_id',
        help='Debit amount for this transaction',
        default=0.0
    )
    credit = fields.Monetary(
        string='Credit',
        currency_field='currency_id',
        help='Credit amount for this transaction',
        default=0.0
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
        required=True,
        domain="[('deprecated', '=', False)]"
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
    ], string='Confidence Level', default='low')

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
    
    is_posted = fields.Boolean(
        string='Is Posted',
        default=False,
        help='Indicates if this reconciled transaction has been posted to accounting'
    )
    
    journal_line_id = fields.Many2one(
        'account.move.line',
        string='Journal Entry Line',
        help='The journal entry line created for this reconciled transaction'
    )
    
    match_score = fields.Integer(
        string='Match Score',
        help='Score indicating how well this transaction matched',
        default=0
    )
    match_criteria = fields.Text(
        string='Match Criteria',
        help='Details of what criteria were matched'
    )
    matched_by_amount = fields.Boolean(string='Matched by Amount', default=False)
    matched_by_reference = fields.Boolean(string='Matched by Reference', default=False)
    matched_by_partner = fields.Boolean(string='Matched by Partner', default=False)
    matched_by_invoice = fields.Boolean(string='Matched by Invoice', default=False)
    matched_by_date = fields.Boolean(string='Matched by Date', default=False)
    matched_by_description = fields.Boolean(string='Matched by Description', default=False)
    matched_by_manual = fields.Boolean(string='Matched Manually', default=False)

    _sql_constraints = [
        ('unique_transaction_id', 'unique(transaction_id)',
         'This transaction is already reconciled. Only one reconciled record per transaction is allowed.'),
    ]

    @api.constrains('debit', 'credit')
    def _check_amounts(self):
        for record in self:
            if record.debit < 0 or record.credit < 0:
                raise ValidationError(_('Debit and Credit amounts cannot be negative.'))
            if record.debit == 0 and record.credit == 0:
                raise ValidationError(_('Debit and Credit cannot both be zero.'))

    @api.depends('debit', 'credit')
    def _compute_amount(self):
        for record in self:
            record.amount = (record.debit or 0.0) - (record.credit or 0.0)

    def action_view_move(self):
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
        self.ensure_one()
        if self.master_id.state == 'completed':
            raise UserError(_('Cannot unreconcile from a completed reconciliation.'))
        
        if self.matched_move_id:
            if self.matched_move_id.state == 'posted':
                try:
                    self.matched_move_id.button_cancel()
                except Exception as e:
                    raise UserError(_('Error cancelling journal entry: %s') % str(e))
            self.matched_move_id.unlink()
        
        if self.matched_move_line_id:
            self.matched_move_line_id.write({
                'is_bank_reconciled': False,
                'bank_reconciliation_id': False,
                'bank_reconciliation_date': False
            })
        
        if self.transaction_id:
            self.transaction_id.write({
                'state': 'matched',
                'reconciled': False,
                'reconciled_date': False,
                'reconciled_by': False,
            })
        
        self.unlink()
        return True

    @api.model
    def create(self, vals):
        # Strict duplicate check - prevent any duplicate creation
        if vals.get('transaction_id'):
            existing = self.search([
                ('transaction_id', '=', vals['transaction_id'])
            ], limit=1)
            if existing:
                raise UserError(_(
                    'This transaction (ID: %s) is already reconciled. '
                    'Cannot create another reconciled record.'
                ) % vals['transaction_id'])
        
        if 'amount' in vals and 'debit' not in vals and 'credit' not in vals:
            if vals['amount'] >= 0:
                vals['debit'] = vals['amount']
                vals['credit'] = 0.0
            else:
                vals['debit'] = 0.0
                vals['credit'] = abs(vals['amount'])
        
        if vals.get('transaction_id'):
            transaction = self.env['bank.reconciliation.transaction'].browse(vals['transaction_id'])
            if transaction.exists():
                vals['match_score'] = transaction.match_score or 0
                vals['matched_by_amount'] = transaction.matched_by_amount or False
                vals['matched_by_reference'] = transaction.matched_by_reference or False
                vals['matched_by_partner'] = transaction.matched_by_partner or False
                vals['matched_by_invoice'] = transaction.matched_by_invoice or False
                vals['matched_by_date'] = transaction.matched_by_date or False
                vals['matched_by_description'] = transaction.matched_by_description or False
                vals['matched_by_manual'] = transaction.matched_by_manual or False
        
        record = super(BankReconciliationReconciled, self).create(vals)
        
        if record.master_id and record.master_id.state == 'completed':
            record.is_posted = True
        
        return record

    def write(self, vals):
        if 'amount' in vals and 'debit' not in vals and 'credit' not in vals:
            if vals['amount'] >= 0:
                vals['debit'] = vals['amount']
                vals['credit'] = 0.0
            else:
                vals['debit'] = 0.0
                vals['credit'] = abs(vals['amount'])
        return super(BankReconciliationReconciled, self).write(vals)

    def unlink(self):
        raise UserError(_('You cannot delete a reconciled transaction.'))
        # for record in self:
        #     if record.is_posted:
        #         raise UserError(_('Cannot delete a posted reconciled transaction.'))
        # return super(BankReconciliationReconciled, self).unlink()