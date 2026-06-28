from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare
import logging

_logger = logging.getLogger(__name__)


class BankReconciliationTransaction(models.Model):
    _name = 'bank.reconciliation.transaction'
    _description = 'Bank Reconciliation Transaction'
    _order = 'date desc, id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    master_id = fields.Many2one(
        'bank.reconciliation.master',
        string='Reconciliation Master',
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
        string='Reference Number'
    )
    payment_reference = fields.Char(
        string='Payment Reference'
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Partner'
    )
    invoice_number = fields.Char(
        string='Invoice Number'
    )
    account_id = fields.Many2one(
        'account.account',
        string='Account',
        domain="[('deprecated', '=', False)]"
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('matched', 'Matched'),
        ('unmatched', 'Unmatched'),
        ('reconciled', 'Reconciled')
    ], string='Status', default='draft', tracking=True)

    confidence_level = fields.Selection([
        ('high', 'High Match'),
        ('medium', 'Medium Match'),
        ('low', 'Low Match')
    ], string='Confidence Level')

    matched_move_id = fields.Many2one(
        'account.move',
        string='Matched Accounting Entry'
    )
    matched_move_line_id = fields.Many2one(
        'account.move.line',
        string='Matched Journal Item'
    )
    reconciled = fields.Boolean(
        string='Reconciled',
        default=False
    )
    reconciled_date = fields.Datetime(
        string='Reconciled Date'
    )
    reconciled_by = fields.Many2one(
        'res.users',
        string='Reconciled By'
    )

    is_adjustment = fields.Boolean(
        string='Is Adjustment Entry'
    )
    adjustment_type = fields.Selection([
        ('bank_charge', 'Bank Charge'),
        ('withholding_tax', 'Withholding Tax'),
        ('interest_income', 'Interest Income'),
        ('miscellaneous', 'Miscellaneous Expense'),
        ('transfer', 'Bank Transfer')
    ], string='Adjustment Type')

    matched_by_amount = fields.Boolean(string='Matched by Amount')
    matched_by_reference = fields.Boolean(string='Matched by Reference')
    matched_by_partner = fields.Boolean(string='Matched by Partner')
    matched_by_invoice = fields.Boolean(string='Matched by Invoice')
    matched_by_date = fields.Boolean(string='Matched by Date')

    in_exception = fields.Boolean(string='In Exception Queue')
    exception_reason = fields.Text(string='Exception Reason')
    follow_up_needed = fields.Boolean(string='Follow-up Needed')
    follow_up_notes = fields.Text(string='Follow-up Notes')

    created_by = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.user
    )
    write_date = fields.Datetime(
        string='Last Modified',
        readonly=True
    )
    previous_account_id = fields.Many2one(
        'account.account',
        string='Previous Account'
    )

    _sql_constraints = [
        ('unique_master_transaction', 'unique(master_id, reference, date, debit, credit)',
         'A transaction with this reference, date, and amount already exists in this reconciliation batch.')
    ]

    @api.depends('debit', 'credit')
    def _compute_amount(self):
        """Compute net amount from debit and credit"""
        for record in self:
            record.amount = (record.debit or 0.0) - (record.credit or 0.0)

    @api.model
    def create(self, vals):
        # Handle backward compatibility - if amount is provided but debit/credit not
        if 'amount' in vals and 'debit' not in vals and 'credit' not in vals:
            if vals['amount'] >= 0:
                vals['debit'] = vals['amount']
                vals['credit'] = 0.0
            else:
                vals['debit'] = 0.0
                vals['credit'] = abs(vals['amount'])
        
        if not vals.get('state'):
            vals['state'] = 'draft'
        return super(BankReconciliationTransaction, self).create(vals)

    def write(self, vals):
        # Handle backward compatibility - if amount is provided but debit/credit not
        if 'amount' in vals and 'debit' not in vals and 'credit' not in vals:
            if vals['amount'] >= 0:
                vals['debit'] = vals['amount']
                vals['credit'] = 0.0
            else:
                vals['debit'] = 0.0
                vals['credit'] = abs(vals['amount'])
        
        if 'account_id' in vals and self.account_id:
            self.previous_account_id = self.account_id.id
        return super(BankReconciliationTransaction, self).write(vals)

    def _auto_match_transactions(self):
        for transaction in self:
            if transaction.state not in ['draft', 'unmatched']:
                continue
            matches = self._find_matching_entries(transaction)
            if matches:
                best_match = self._select_best_match(matches)
                transaction._apply_match(best_match)
            else:
                transaction.state = 'unmatched'
                transaction.confidence_level = 'low'

    def _find_matching_entries(self, transaction):
        matches = []
        domain = [
            ('reconciled', '=', False),
            ('company_id', '=', transaction.company_id.id)
        ]
        
        # If account_id is set, use it in search
        if transaction.account_id:
            domain.append(('account_id', '=', transaction.account_id.id))
            
        matching_moves = self.env['account.move.line'].search(domain)
        
        for move_line in matching_moves:
            score = 0
            criteria = {}
            
            # Match by debit/credit instead of amount
            if transaction.debit and move_line.debit:
                if float_compare(move_line.debit, transaction.debit, precision_digits=2) == 0:
                    score += 30
                    criteria['amount'] = True
            elif transaction.credit and move_line.credit:
                if float_compare(move_line.credit, transaction.credit, precision_digits=2) == 0:
                    score += 30
                    criteria['amount'] = True
            # Fallback to amount comparison for backward compatibility
            elif float_compare(abs(move_line.balance), abs(transaction.amount), precision_digits=2) == 0:
                score += 30
                criteria['amount'] = True
                
            if transaction.reference and move_line.move_id.ref:
                if transaction.reference.lower() in move_line.move_id.ref.lower():
                    score += 20
                    criteria['reference'] = True
            if transaction.partner_id and move_line.partner_id:
                if transaction.partner_id.id == move_line.partner_id.id:
                    score += 20
                    criteria['partner'] = True
            if transaction.invoice_number:
                if move_line.move_id.invoice_origin:
                    if transaction.invoice_number in move_line.move_id.invoice_origin:
                        score += 15
                        criteria['invoice'] = True
                if move_line.move_id.name:
                    if transaction.invoice_number in move_line.move_id.name:
                        score += 10
                        criteria['invoice'] = True
            if transaction.payment_reference and move_line.move_id.payment_reference:
                if transaction.payment_reference in move_line.move_id.payment_reference:
                    score += 10
                    criteria['payment'] = True
            if transaction.date and move_line.date:
                date_diff = abs((transaction.date - move_line.date).days)
                if date_diff <= 3:
                    score += 5
                    criteria['date'] = True
                elif date_diff <= 7:
                    score += 3
                    criteria['date'] = True
            if score > 0:
                matches.append({
                    'move_line': move_line,
                    'move': move_line.move_id,
                    'score': score,
                    'criteria': criteria,
                    'balance': move_line.balance,
                    'debit': move_line.debit,
                    'credit': move_line.credit,
                    'date': move_line.date
                })
        return sorted(matches, key=lambda x: x['score'], reverse=True)

    def _select_best_match(self, matches):
        if not matches:
            return None
        best_match = matches[0]
        high_score_matches = [m for m in matches if m['score'] == best_match['score']]
        if len(high_score_matches) > 1:
            exact_amount = [m for m in high_score_matches if m['criteria'].get('amount')]
            if exact_amount:
                return exact_amount[0]
        return best_match

    def _apply_match(self, match):
        if not match:
            return
        self.write({
            'state': 'matched',
            'matched_move_id': match['move'].id,
            'matched_move_line_id': match['move_line'].id,
            'matched_by_amount': match['criteria'].get('amount', False),
            'matched_by_reference': match['criteria'].get('reference', False),
            'matched_by_partner': match['criteria'].get('partner', False),
            'matched_by_invoice': match['criteria'].get('invoice', False),
            'matched_by_date': match['criteria'].get('date', False),
        })
        if match['score'] >= 60:
            self.confidence_level = 'high'
        elif match['score'] >= 40:
            self.confidence_level = 'medium'
        else:
            self.confidence_level = 'low'

    def action_accept_match(self):
        self.ensure_one()
        if self.state != 'matched':
            raise UserError(_('Only matched transactions can be accepted.'))
        if not self.account_id:
            raise UserError(_('Please select an account for this transaction.'))
        
        # Create reconciled record
        self._create_reconciled_record()
        
        self.state = 'reconciled'
        self.reconciled = True
        self.reconciled_date = fields.Datetime.now()
        self.reconciled_by = self.env.user
        
        return True

    def _create_reconciled_record(self):
        self.ensure_one()
        Reconciled = self.env['bank.reconciliation.reconciled']
        vals = {
            'master_id': self.master_id.id,
            'transaction_id': self.id,
            'date': self.date,
            'description': self.description,
            'debit': self.debit or 0.0,
            'credit': self.credit or 0.0,
            'amount': self.amount,
            'account_id': self.account_id.id,
            'matched_move_id': self.matched_move_id.id,
            'matched_move_line_id': self.matched_move_line_id.id,
            'reconciled_by': self.env.user.id,
            'reconciliation_date': fields.Datetime.now(),
            'reference': self.reference,
            'partner_id': self.partner_id.id,
            'confidence_level': self.confidence_level,
            'adjustment_type': self.adjustment_type,
        }
        return Reconciled.create(vals)

    def action_reject_match(self):
        self.ensure_one()
        if self.state != 'matched':
            raise UserError(_('Only matched transactions can be rejected.'))
        self.write({
            'state': 'unmatched',
            'matched_move_id': False,
            'matched_move_line_id': False,
            'matched_by_amount': False,
            'matched_by_reference': False,
            'matched_by_partner': False,
            'matched_by_invoice': False,
            'matched_by_date': False,
            'confidence_level': 'low'
        })
        return True

    def action_manual_reconcile(self):
        self.ensure_one()
        if self.state not in ['matched', 'unmatched']:
            raise UserError(_('Only matched or unmatched transactions can be reconciled.'))
        if not self.account_id:
            raise UserError(_('Please select an account for this transaction.'))
        
        # Create reconciled record directly
        self._create_reconciled_record()
        self.state = 'reconciled'
        self.reconciled = True
        self.reconciled_date = fields.Datetime.now()
        self.reconciled_by = self.env.user
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bank.reconciliation.master',
            'res_id': self.master_id.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def action_view_related_move(self):
        self.ensure_one()
        if not self.matched_move_id:
            raise UserError(_('No related accounting entry found.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.matched_move_id.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def action_show_unreconciled_entries(self):
        self.ensure_one()
        if not self.account_id:
            raise UserError(_('Please select an account first.'))
        domain = [
            ('account_id', '=', self.account_id.id),
            ('reconciled', '=', False),
            ('company_id', '=', self.company_id.id)
        ]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {'search_default_unreconciled': 1}
        }

    @api.onchange('debit', 'credit')
    def _onchange_debit_credit(self):
        """Update amount when debit or credit changes"""
        if self.debit or self.credit:
            self.amount = (self.debit or 0.0) - (self.credit or 0.0)