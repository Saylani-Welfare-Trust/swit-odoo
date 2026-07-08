from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class BankReconciliationTransaction(models.Model):
    _name = 'bank.reconciliation.transaction'
    _description = 'Bank Reconciliation Transaction'
    _order = 'date desc, id'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'description'

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
    ], string='Confidence Level', default='low')

    matched_move_id = fields.Many2one(
        'account.move',
        string='Matched Accounting Entry'
    )
    matched_move_line_id = fields.Many2one(
        'account.move.line',
        string='Matched Journal Item'
    )
    matched_move_line_name = fields.Char(
        string='Matched Line Description',
        compute='_compute_matched_line_info',
        store=False
    )
    matched_move_ref = fields.Char(
        string='Matched Entry Reference',
        compute='_compute_matched_line_info',
        store=False
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
    
    is_already_reconciled = fields.Boolean(
        string='Already Reconciled',
        compute='_compute_is_already_reconciled',
        store=False
    )

    is_adjustment = fields.Boolean(
        string='Is Adjustment Entry',
        default=False
    )
    adjustment_type = fields.Selection([
        ('bank_charge', 'Bank Charge'),
        ('withholding_tax', 'Withholding Tax'),
        ('interest_income', 'Interest Income'),
        ('miscellaneous', 'Miscellaneous Expense'),
        ('transfer', 'Bank Transfer')
    ], string='Adjustment Type')

    matched_by_amount = fields.Boolean(string='Matched by Amount', default=False)
    matched_by_reference = fields.Boolean(string='Matched by Reference', default=False)
    matched_by_partner = fields.Boolean(string='Matched by Partner', default=False)
    matched_by_invoice = fields.Boolean(string='Matched by Invoice', default=False)
    matched_by_date = fields.Boolean(string='Matched by Date', default=False)
    matched_by_description = fields.Boolean(string='Matched by Description', default=False)
    matched_by_manual = fields.Boolean(string='Matched Manually', default=False)
    match_score = fields.Integer(string='Match Score', default=0)

    in_exception = fields.Boolean(string='In Exception Queue', default=False)
    exception_reason = fields.Text(string='Exception Reason')
    follow_up_needed = fields.Boolean(string='Follow-up Needed', default=False)
    follow_up_notes = fields.Text(string='Follow-up Notes')

    created_by = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.user,
        readonly=True
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

    @api.depends('matched_move_line_id')
    def _compute_matched_line_info(self):
        for record in self:
            if record.matched_move_line_id:
                record.matched_move_line_name = record.matched_move_line_id.name or ''
                record.matched_move_ref = record.matched_move_line_id.move_id.ref or ''
            else:
                record.matched_move_line_name = False
                record.matched_move_ref = False

    def _compute_is_already_reconciled(self):
        for record in self:
            record.is_already_reconciled = self.env['bank.reconciliation.reconciled'].search_count([
                ('transaction_id', '=', record.id)
            ]) > 0

    @api.model
    def create(self, vals):
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
            # Skip if already reconciled
            if transaction.state == 'reconciled':
                continue
            # Skip if already has reconciled record
            if self.env['bank.reconciliation.reconciled'].search_count([('transaction_id', '=', transaction.id)]) > 0:
                continue
            if transaction.state not in ['draft', 'unmatched']:
                continue
            
            matches = transaction._find_matching_move_lines()
            if matches:
                best_match = transaction._select_best_match(matches)
                if best_match:
                    transaction._apply_match(best_match, manual=False)
                else:
                    transaction.write({
                        'state': 'unmatched',
                        'confidence_level': 'low'
                    })
            else:
                transaction.write({
                    'state': 'unmatched',
                    'confidence_level': 'low'
                })

    def _find_matching_move_lines(self):
        """Find matching account move lines - EXCLUDING already reconciled ones"""
        self.ensure_one()
        matches = []
        
        # Build search domain - EXCLUDE reconciled move lines
        domain = [
            ('is_bank_reconciled', '=', False),  # This is the key - exclude reconciled entries
            ('reconciled', '=', False),  # This is the key - exclude reconciled entries
            ('company_id', '=', self.company_id.id)
        ]
        
        if self.account_id:
            domain.append(('account_id', '=', self.account_id.id))
        else:
            domain.append(('account_id', '!=', False))
        
        if self.date:
            days = self.master_id.match_tolerance_days or 3
            from_date = self.date - timedelta(days=days)
            to_date = self.date + timedelta(days=days)
            domain.append(('date', '>=', from_date))
            domain.append(('date', '<=', to_date))
        
        # Also exclude move lines that are already linked to reconciled records
        reconciled_line_ids = self.env['bank.reconciliation.reconciled'].search([
            ('matched_move_line_id', '!=', False)
        ]).mapped('matched_move_line_id.id')
        
        if reconciled_line_ids:
            domain.append(('id', 'not in', reconciled_line_ids))
        
        move_lines = self.env['account.move.line'].search(domain, limit=1000)
        
        for move_line in move_lines:
            # Double check that the move line is not reconciled
            if move_line.reconciled:
                continue
            if move_line.id in reconciled_line_ids:
                continue
            
            score = 0
            criteria = {}
            
            if self.master_id.match_by_amount and self._check_amount_match(move_line):
                score += 30
                criteria['amount'] = True
            
            if self.master_id.match_by_reference and self._check_reference_match(move_line):
                score += 20
                criteria['reference'] = True
            
            if self.master_id.match_by_partner and self._check_partner_match(move_line):
                score += 20
                criteria['partner'] = True
            
            if self.master_id.match_by_invoice and self._check_invoice_match(move_line):
                score += 15
                criteria['invoice'] = True
            
            if self._check_payment_match(move_line):
                score += 10
                criteria['payment'] = True
            
            if self.master_id.match_by_date and self._check_date_match(move_line):
                score += 5
                criteria['date'] = True
            
            if self._check_description_match(move_line):
                score += 5
                criteria['description'] = True
            
            if score > 0:
                matches.append({
                    'move_line': move_line,
                    'move': move_line.move_id,
                    'score': score,
                    'criteria': criteria,
                    'balance': move_line.balance,
                    'debit': move_line.debit,
                    'credit': move_line.credit,
                    'date': move_line.date,
                    'move_line_display': move_line.display_name or move_line.name,
                    'move_ref': move_line.move_id.ref or '',
                })
        return sorted(matches, key=lambda x: x['score'], reverse=True)

    def _check_amount_match(self, move_line):
        if self.debit and move_line.debit:
            if abs(move_line.debit - self.debit) <= (self.master_id.match_tolerance_amount or 0.01):
                return True
        if self.credit and move_line.credit:
            if abs(move_line.credit - self.credit) <= (self.master_id.match_tolerance_amount or 0.01):
                return True
        if float_compare(abs(move_line.balance), abs(self.amount), precision_digits=2) == 0:
            return True
        return False

    def _check_reference_match(self, move_line):
        if not self.reference:
            return False
        move_ref = move_line.move_id.ref or ''
        if self.reference.lower() in move_ref.lower():
            return True
        return False

    def _check_partner_match(self, move_line):
        if not self.partner_id:
            return False
        if move_line.partner_id and move_line.partner_id.id == self.partner_id.id:
            return True
        return False

    def _check_invoice_match(self, move_line):
        if not self.invoice_number:
            return False
        invoice_origin = move_line.move_id.invoice_origin or ''
        move_name = move_line.move_id.name or ''
        if self.invoice_number in invoice_origin or self.invoice_number in move_name:
            return True
        return False

    def _check_payment_match(self, move_line):
        if not self.payment_reference:
            return False
        payment_ref = move_line.move_id.payment_reference or ''
        if self.payment_reference in payment_ref:
            return True
        return False

    def _check_date_match(self, move_line):
        if not self.date or not move_line.date:
            return False
        days = self.master_id.match_tolerance_days or 3
        date_diff = abs((self.date - move_line.date).days)
        if date_diff <= days:
            return True
        return False

    def _check_description_match(self, move_line):
        if not self.description or not move_line.name:
            return False
        keywords = self.description.lower().split()
        move_text = move_line.name.lower()
        match_count = sum(1 for keyword in keywords if keyword in move_text)
        if match_count >= len(keywords) * 0.5:
            return True
        return False

    def _select_best_match(self, matches):
        if not matches:
            return None
        best_match = matches[0]
        high_score_matches = [m for m in matches if m['score'] == best_match['score']]
        if len(high_score_matches) > 1:
            exact_amount = [m for m in high_score_matches if m['criteria'].get('amount')]
            if exact_amount:
                return exact_amount[0]
            partner_match = [m for m in high_score_matches if m['criteria'].get('partner')]
            if partner_match:
                return partner_match[0]
        return best_match

    def _apply_match(self, match, manual=True):
        """Apply the match to this transaction"""
        if not match:
            return
        
        # Prevent re-reconciliation
        if self.state == 'reconciled':
            return
        
        if self.env['bank.reconciliation.reconciled'].search_count([('transaction_id', '=', self.id)]) > 0:
            return
        
        if manual:
            self.write({
                'state': 'matched',
                'matched_move_id': match['move'].id if isinstance(match, dict) and match.get('move') else False,
                'matched_move_line_id': match['move_line'].id if isinstance(match, dict) and match.get('move_line') else False,
                'matched_by_manual': True,
                'confidence_level': 'high',
                'match_score': 100,
                'matched_by_amount': True,
                'matched_by_reference': False,
                'matched_by_partner': False,
                'matched_by_invoice': False,
                'matched_by_date': False,
                'matched_by_description': False,
            })
        else:
            self.write({
                'state': 'matched',
                'matched_move_id': match['move'].id,
                'matched_move_line_id': match['move_line'].id,
                'matched_by_amount': match['criteria'].get('amount', False),
                'matched_by_reference': match['criteria'].get('reference', False),
                'matched_by_partner': match['criteria'].get('partner', False),
                'matched_by_invoice': match['criteria'].get('invoice', False),
                'matched_by_date': match['criteria'].get('date', False),
                'matched_by_description': match['criteria'].get('description', False),
                'matched_by_manual': False,
                'match_score': match['score'],
            })
            
            if match['score'] >= 60:
                self.confidence_level = 'high'
            elif match['score'] >= 40:
                self.confidence_level = 'medium'
            else:
                self.confidence_level = 'low'

    def action_manual_match(self):
        self.ensure_one()
        if self.state == 'reconciled':
            raise UserError(_('This transaction is already reconciled.'))
        if self.env['bank.reconciliation.reconciled'].search_count([('transaction_id', '=', self.id)]) > 0:
            raise UserError(_('This transaction already has a reconciled record. Cannot reconcile again.'))
        
        return {
            'name': _('Manual Match'),
            'type': 'ir.actions.act_window',
            'res_model': 'reconcile.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_master_id': self.master_id.id,
                'default_transaction_id': self.id,
                'default_account_id': self.account_id.id if self.account_id else False,
                'default_create_journal_entry': True,
            }
        }

    def action_accept_match(self):
        self.ensure_one()
        if self.state == 'reconciled':
            raise UserError(_('This transaction is already reconciled.'))
        if self.state != 'matched':
            raise UserError(_('Only matched transactions can be accepted.'))
        if not self.account_id:
            raise UserError(_('Please select an account for this transaction.'))
        
        existing_reconciled = self.env['bank.reconciliation.reconciled'].search([
            ('transaction_id', '=', self.id)
        ], limit=1)
        if existing_reconciled:
            raise UserError(_('This transaction already has a reconciled record. Cannot reconcile again.'))
        
        self._create_reconciled_record()
        
        self.write({
            'state': 'reconciled',
            'reconciled': True,
            'reconciled_date': fields.Datetime.now(),
            'reconciled_by': self.env.user.id,
        })
        
        return True

    def action_accept_and_create_journal(self):
        self.ensure_one()
        if self.state == 'reconciled':
            raise UserError(_('This transaction is already reconciled.'))
        if self.state != 'matched':
            raise UserError(_('Only matched transactions can be accepted.'))
        if not self.account_id:
            raise UserError(_('Please select an account for this transaction.'))
        
        existing_reconciled = self.env['bank.reconciliation.reconciled'].search([
            ('transaction_id', '=', self.id)
        ], limit=1)
        if existing_reconciled:
            raise UserError(_('This transaction already has a reconciled record. Cannot reconcile again.'))
        
        reconciled = self._create_reconciled_record()
        
        self.write({
            'state': 'reconciled',
            'reconciled': True,
            'reconciled_date': fields.Datetime.now(),
            'reconciled_by': self.env.user.id,
        })
        
        if reconciled:
            self._create_journal_entry_for_transaction(reconciled)
        
        return True

    def _create_reconciled_record(self):
        self.ensure_one()
        existing = self.env['bank.reconciliation.reconciled'].search([
            ('transaction_id', '=', self.id)
        ], limit=1)
        if existing:
            raise UserError(_('This transaction already has a reconciled record. Cannot reconcile again.'))
        
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
            'match_score': self.match_score,
            'matched_by_amount': self.matched_by_amount,
            'matched_by_reference': self.matched_by_reference,
            'matched_by_partner': self.matched_by_partner,
            'matched_by_invoice': self.matched_by_invoice,
            'matched_by_date': self.matched_by_date,
            'matched_by_description': self.matched_by_description,
            'matched_by_manual': self.matched_by_manual,
        }
        return Reconciled.create(vals)

    def _create_journal_entry_for_transaction(self, reconciled):
        self.ensure_one()
        if not reconciled:
            return
        if reconciled.is_posted:
            return
        if reconciled.matched_move_id:
            return
        
        journal = self.master_id.journal_id
        if not journal:
            raise UserError(_('No journal found for this reconciliation.'))
        
        move_lines = []
        
        if reconciled.debit > 0:
            move_lines.append((0, 0, {
                'account_id': reconciled.account_id.id,
                'partner_id': reconciled.partner_id.id if reconciled.partner_id else False,
                'debit': reconciled.debit,
                'credit': 0.0,
                'name': _('%s - %s') % (self.master_id.name, self.description[:50]),
                'date': self.date or fields.Date.today(),
                'is_bank_reconciled': True,
                'bank_reconciliation_id': self.master_id.id,
                'bank_reconciliation_date': self.master_id.date,
            }))
            move_lines.append((0, 0, {
                'account_id': self.master_id.posted_account_id.id,
                'partner_id': reconciled.partner_id.id if reconciled.partner_id else False,
                'debit': 0.0,
                'credit': reconciled.debit,
                'name': _('Contra: %s') % self.master_id.posted_account_id.name,
                'date': self.date or fields.Date.today(),
                'is_bank_reconciled': True,
                'bank_reconciliation_id': self.master_id.id,
                'bank_reconciliation_date': self.master_id.date,
            }))
        
        if reconciled.credit > 0:
            move_lines.append((0, 0, {
                'account_id': reconciled.account_id.id,
                'partner_id': reconciled.partner_id.id if reconciled.partner_id else False,
                'debit': 0.0,
                'credit': reconciled.credit,
                'name': _('%s - %s') % (self.master_id.name, self.description[:50]),
                'date': self.date or fields.Date.today(),
                'is_bank_reconciled': True,
                'bank_reconciliation_id': self.master_id.id,
                'bank_reconciliation_date': self.master_id.date,
            }))
            move_lines.append((0, 0, {
                'account_id': self.master_id.posted_account_id.id,
                'partner_id': reconciled.partner_id.id if reconciled.partner_id else False,
                'debit': reconciled.credit,
                'credit': 0.0,
                'name': _('Contra: %s') % self.master_id.posted_account_id.name,
                'date': self.date or fields.Date.today(),
                'is_bank_reconciled': True,
                'bank_reconciliation_id': self.master_id.id,
                'bank_reconciliation_date': self.master_id.date,
            }))
        
        if len(move_lines) < 2:
            raise UserError(_('Cannot create journal entry: Need at least two lines for a balanced entry.'))
        
        total_debit = sum(line[2]['debit'] for line in move_lines)
        total_credit = sum(line[2]['credit'] for line in move_lines)
        if abs(total_debit - total_credit) > 0.01:
            raise UserError(_('Journal entry is not balanced. Debit: %s, Credit: %s') % (total_debit, total_credit))
        
        try:
            move = self.env['account.move'].create({
                'journal_id': journal.id,
                'date': self.date or fields.Date.today(),
                'ref': '%s - %s' % (self.master_id.name, self.reference or self.id),
                'company_id': self.master_id.company_id.id,
                'line_ids': move_lines,
                'narration': _('Bank Reconciliation: %s - Transaction: %s') % (
                    self.master_id.name, self.description[:100]
                ),
                'state': 'draft',
            })
            move.action_post()
            
            reconciled.write({
                'matched_move_id': move.id,
                'is_posted': True,
            })
            
            for line in move.line_ids:
                if line.account_id.id == reconciled.account_id.id:
                    reconciled.journal_line_id = line.id
                    break
            
            self.matched_move_id = move.id
            
        except Exception as e:
            raise UserError(_('Error creating journal entry: %s') % str(e))

    def action_reject_match(self):
        self.ensure_one()
        if self.state == 'reconciled':
            raise UserError(_('Cannot reject a reconciled transaction. Please unreconcile first.'))
        if self.state != 'matched':
            raise UserError(_('Only matched transactions can be rejected.'))
        
        existing_reconciled = self.env['bank.reconciliation.reconciled'].search([
            ('transaction_id', '=', self.id)
        ])
        if existing_reconciled:
            existing_reconciled.unlink()
        
        self.write({
            'state': 'unmatched',
            'matched_move_id': False,
            'matched_move_line_id': False,
            'matched_by_amount': False,
            'matched_by_reference': False,
            'matched_by_partner': False,
            'matched_by_invoice': False,
            'matched_by_date': False,
            'matched_by_description': False,
            'matched_by_manual': False,
            'match_score': 0,
            'confidence_level': 'low'
        })
        return True

    def action_manual_reconcile(self):
        self.ensure_one()
        if self.state == 'reconciled':
            raise UserError(_('This transaction is already reconciled.'))
        if self.state not in ['matched', 'unmatched']:
            raise UserError(_('Only matched or unmatched transactions can be reconciled.'))
        if not self.account_id:
            raise UserError(_('Please select an account for this transaction.'))
        if self.env['bank.reconciliation.reconciled'].search_count([('transaction_id', '=', self.id)]) > 0:
            raise UserError(_('This transaction already has a reconciled record. Cannot reconcile again.'))
        
        if self.state == 'unmatched':
            return self.action_manual_match()
        
        if self.state == 'matched':
            self.action_accept_match()

    def action_unreconcile(self):
        self.ensure_one()
        if self.state != 'reconciled':
            raise UserError(_('Only reconciled transactions can be unreconciled.'))
        
        reconciled = self.env['bank.reconciliation.reconciled'].search([
            ('transaction_id', '=', self.id)
        ], limit=1)
        if reconciled:
            if reconciled.matched_move_id:
                try:
                    if reconciled.matched_move_id.state == 'posted':
                        reconciled.matched_move_id.button_cancel()
                    reconciled.matched_move_id.unlink()
                except Exception as e:
                    _logger.warning("Could not delete journal entry: %s", str(e))
            reconciled.unlink()
        
        self.write({
            'state': 'matched',
            'reconciled': False,
            'reconciled_date': False,
            'reconciled_by': False,
        })
        return True

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

    def action_view_related_move_line(self):
        self.ensure_one()
        if not self.matched_move_line_id:
            raise UserError(_('No related journal item found.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'res_id': self.matched_move_line_id.id,
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
            ('is_bank_reconciled', '=', False),
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
        if self.debit or self.credit:
            self.amount = (self.debit or 0.0) - (self.credit or 0.0)