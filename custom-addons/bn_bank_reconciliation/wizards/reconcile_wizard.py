from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class ReconcileWizard(models.TransientModel):
    _name = 'reconcile.wizard'
    _description = 'Reconciliation Wizard'

    master_id = fields.Many2one(
        'bank.reconciliation.master',
        string='Reconciliation Master',
        required=True
    )
    transaction_id = fields.Many2one(
        'bank.reconciliation.transaction',
        string='Transaction'
    )
    account_id = fields.Many2one(
        'account.account',
        string='Account',
        required=True,
        domain="[('deprecated', '=', False)]"
    )

    unreconciled_line_ids = fields.Many2many(
        'account.move.line',
        string='Unreconciled Entries',
        compute='_compute_unreconciled_lines',
        store=False
    )
    selected_line_ids = fields.Many2many(
        'account.move.line',
        string='Selected Entries',
        domain="[('id', 'in', unreconciled_line_ids)]"
    )

    date_from = fields.Date(string='Date From')
    date_to = fields.Date(string='Date To')
    partner_id = fields.Many2one('res.partner', string='Partner')
    show_only_matching_amount = fields.Boolean(
        string='Show Only Matching Amount',
        default=True
    )
    
    # Debit/Credit matching options
    match_type = fields.Selection([
        ('net', 'Match Net Amount'),
        ('debit_credit', 'Match Debit/Credit Separately')
    ], string='Match Type', default='net')
    
    # Journal entry options
    create_journal_entry = fields.Boolean(
        string='Create Journal Entry',
        default=True,
        help='Create a journal entry for this reconciliation'
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        domain="[('type', 'in', ['bank', 'cash', 'general'])]"
    )

    @api.depends('account_id', 'date_from', 'date_to', 'partner_id', 'transaction_id', 'match_type')
    def _compute_unreconciled_lines(self):
        for wizard in self:
            domain = [
                ('account_id', '=', wizard.account_id.id),
                ('reconciled', '=', False),
                ('company_id', '=', wizard.master_id.company_id.id)
            ]
            if wizard.date_from:
                domain.append(('date', '>=', wizard.date_from))
            if wizard.date_to:
                domain.append(('date', '<=', wizard.date_to))
            if wizard.partner_id:
                domain.append(('partner_id', '=', wizard.partner_id.id))
            
            lines = self.env['account.move.line'].search(domain)
            
            if wizard.show_only_matching_amount and wizard.transaction_id:
                matching_lines = self.env['account.move.line']
                
                if wizard.match_type == 'debit_credit':
                    # Match by debit and credit separately
                    if wizard.transaction_id.debit:
                        debit_lines = lines.filtered(
                            lambda l: abs(l.debit - wizard.transaction_id.debit) < 0.01
                        )
                        matching_lines |= debit_lines
                    
                    if wizard.transaction_id.credit:
                        credit_lines = lines.filtered(
                            lambda l: abs(l.credit - wizard.transaction_id.credit) < 0.01
                        )
                        matching_lines |= credit_lines
                    
                    if not matching_lines:
                        matching_lines = lines.filtered(
                            lambda l: abs(abs(l.balance) - abs(wizard.transaction_id.amount)) < 0.01
                        )
                else:
                    transaction_amount = abs(wizard.transaction_id.amount)
                    matching_lines = lines.filtered(
                        lambda l: abs(abs(l.balance) - transaction_amount) < 0.01
                    )
                
                wizard.unreconciled_line_ids = matching_lines
            else:
                wizard.unreconciled_line_ids = lines
            
            # Set default journal from master if not set
            if not wizard.journal_id and wizard.master_id:
                wizard.journal_id = wizard.master_id.journal_id.id

    def action_reconcile(self):
        self.ensure_one()
        if not self.selected_line_ids:
            raise UserError(_('Please select at least one accounting entry to reconcile.'))
        if self.transaction_id:
            return self._reconcile_single_transaction()
        else:
            return self._reconcile_multiple_transactions()

    def _reconcile_single_transaction(self):
        self.ensure_one()
        transaction = self.transaction_id
        
        if transaction.state == 'reconciled':
            raise UserError(_('This transaction is already reconciled.'))
        
        # Validate the selected lines match the transaction
        if self.match_type == 'debit_credit':
            total_debit = sum(line.debit for line in self.selected_line_ids)
            total_credit = sum(line.credit for line in self.selected_line_ids)
            
            if transaction.debit and abs(transaction.debit - total_debit) > 0.01:
                raise UserError(_(
                    'Total debit amount (%s) does not match transaction debit (%s). '
                    'Please select entries that sum to the transaction debit amount.'
                ) % (total_debit, transaction.debit))
            
            if transaction.credit and abs(transaction.credit - total_credit) > 0.01:
                raise UserError(_(
                    'Total credit amount (%s) does not match transaction credit (%s). '
                    'Please select entries that sum to the transaction credit amount.'
                ) % (total_credit, transaction.credit))
            
            if not transaction.debit and not transaction.credit:
                raise UserError(_('Transaction has no debit or credit amount.'))
        else:
            total_selected = sum(abs(line.balance) for line in self.selected_line_ids)
            transaction_amount = abs(transaction.amount)
            
            if abs(total_selected - transaction_amount) > 0.01:
                raise UserError(_(
                    'Total selected amount (%s) does not match transaction amount (%s). '
                    'Please select entries that sum to the transaction amount.'
                ) % (total_selected, transaction_amount))
        
        # Mark the selected lines as bank reconciled
        for line in self.selected_line_ids:
            line.write({
                'is_bank_reconciled': True,
                'bank_reconciliation_id': self.master_id.id,
                'bank_reconciliation_date': fields.Date.today()
            })
        
        # Get the first selected line for reference
        first_line = self.selected_line_ids[0] if self.selected_line_ids else False
        
        # Update the transaction
        transaction.write({
            'state': 'reconciled',
            'reconciled': True,
            'reconciled_date': fields.Datetime.now(),
            'reconciled_by': self.env.user,
            'matched_move_id': first_line.move_id.id if first_line else False,
            'matched_move_line_id': first_line.id if first_line else False,
        })
        
        # Create reconciled record
        reconciled = transaction._create_reconciled_record()
        
        # Create journal entry if requested
        if self.create_journal_entry:
            self._create_journal_entry_for_reconciliation(transaction, reconciled)
        
        return {
            'type': 'ir.actions.act_window_close'
        }

    def _reconcile_multiple_transactions(self):
        self.ensure_one()
        
        total_selected_debit = sum(line.debit for line in self.selected_line_ids)
        total_selected_credit = sum(line.credit for line in self.selected_line_ids)
        total_selected_amount = sum(abs(line.balance) for line in self.selected_line_ids)
        
        unmatched_trans = self.master_id.transaction_ids.filtered(
            lambda t: t.state in ['matched', 'unmatched'] and t.account_id == self.account_id
        )
        
        if not unmatched_trans:
            raise UserError(_('No unmatched transactions found for this account.'))
        
        matching_trans = self.env['bank.reconciliation.transaction']
        
        if self.match_type == 'debit_credit':
            for trans in unmatched_trans:
                if abs(trans.debit - total_selected_debit) < 0.01 and abs(trans.credit - total_selected_credit) < 0.01:
                    matching_trans |= trans
        else:
            for trans in unmatched_trans:
                if abs(abs(trans.amount) - total_selected_amount) < 0.01:
                    matching_trans |= trans
        
        if not matching_trans:
            raise UserError(_(
                'No unmatched transaction found matching the selected entries total:\n'
                'Total Debit: %s, Total Credit: %s, Net: %s'
            ) % (total_selected_debit, total_selected_credit, total_selected_amount))
        
        trans = matching_trans[0]
        
        for line in self.selected_line_ids:
            line.write({
                'is_bank_reconciled': True,
                'bank_reconciliation_id': self.master_id.id,
                'bank_reconciliation_date': fields.Date.today()
            })
        
        first_line = self.selected_line_ids[0] if self.selected_line_ids else False
        
        trans.write({
            'state': 'reconciled',
            'reconciled': True,
            'reconciled_date': fields.Datetime.now(),
            'reconciled_by': self.env.user,
            'matched_move_id': first_line.move_id.id if first_line else False,
            'matched_move_line_id': first_line.id if first_line else False,
        })
        
        reconciled = trans._create_reconciled_record()
        
        if self.create_journal_entry:
            self._create_journal_entry_for_reconciliation(trans, reconciled)
        
        return {
            'type': 'ir.actions.act_window_close'
        }

    def _create_journal_entry_for_reconciliation(self, transaction, reconciled):
        """Create a journal entry for the reconciled transaction"""
        self.ensure_one()
        
        # Get journal from wizard or master
        journal = self.journal_id or self.master_id.journal_id
        if not journal:
            raise UserError(_('Please select a journal for the journal entry.'))
        
        # Prepare journal entry lines
        move_lines = []
        
        # Debit/Credit for the transaction account
        if reconciled.debit > 0:
            move_lines.append((0, 0, {
                'account_id': reconciled.account_id.id,
                'partner_id': reconciled.partner_id.id if reconciled.partner_id else False,
                'debit': reconciled.debit,
                'credit': 0.0,
                'name': _('%s - %s') % (transaction.master_id.name, transaction.description[:50]),
                'date': transaction.date or fields.Date.today(),
            }))
        
        if reconciled.credit > 0:
            move_lines.append((0, 0, {
                'account_id': reconciled.account_id.id,
                'partner_id': reconciled.partner_id.id if reconciled.partner_id else False,
                'debit': 0.0,
                'credit': reconciled.credit,
                'name': _('%s - %s') % (transaction.master_id.name, transaction.description[:50]),
                'date': transaction.date or fields.Date.today(),
            }))
        
        # Contra entry in posted account
        if reconciled.debit > 0:
            move_lines.append((0, 0, {
                'account_id': transaction.master_id.posted_account_id.id,
                'partner_id': reconciled.partner_id.id if reconciled.partner_id else False,
                'debit': 0.0,
                'credit': reconciled.debit,
                'name': _('Contra: %s') % transaction.master_id.posted_account_id.name,
                'date': transaction.date or fields.Date.today(),
            }))
        
        if reconciled.credit > 0:
            move_lines.append((0, 0, {
                'account_id': transaction.master_id.posted_account_id.id,
                'partner_id': reconciled.partner_id.id if reconciled.partner_id else False,
                'debit': reconciled.credit,
                'credit': 0.0,
                'name': _('Contra: %s') % transaction.master_id.posted_account_id.name,
                'date': transaction.date or fields.Date.today(),
            }))
        
        # Add bank account line if needed
        # This handles the case where the reconciliation should affect the bank account
        # Comment this out if you don't want to affect the bank account directly
        """
        if reconciled.debit > 0:
            move_lines.append((0, 0, {
                'account_id': transaction.master_id.account_id.id,
                'partner_id': reconciled.partner_id.id if reconciled.partner_id else False,
                'debit': 0.0,
                'credit': reconciled.debit,
                'name': _('Bank: %s') % transaction.master_id.account_id.name,
                'date': transaction.date or fields.Date.today(),
            }))
        
        if reconciled.credit > 0:
            move_lines.append((0, 0, {
                'account_id': transaction.master_id.account_id.id,
                'partner_id': reconciled.partner_id.id if reconciled.partner_id else False,
                'debit': reconciled.credit,
                'credit': 0.0,
                'name': _('Bank: %s') % transaction.master_id.account_id.name,
                'date': transaction.date or fields.Date.today(),
            }))
        """
        
        # Create the journal entry
        move_vals = {
            'journal_id': journal.id,
            'date': transaction.date or fields.Date.today(),
            'ref': '%s - %s' % (transaction.master_id.name, transaction.reference or transaction.id),
            'company_id': transaction.master_id.company_id.id,
            'line_ids': move_lines,
            'narration': _('Bank Reconciliation: %s - Transaction: %s') % (
                transaction.master_id.name, 
                transaction.description[:100]
            ),
            'state': 'draft',
        }
        
        try:
            move = self.env['account.move'].create(move_vals)
            move.action_post()
            
            # Update the reconciled record with the move reference
            reconciled.matched_move_id = move.id
            reconciled.is_posted = True
            
            # Find and save the specific journal line for this transaction
            for line in move.line_ids:
                if line.account_id.id == reconciled.account_id.id:
                    reconciled.journal_line_id = line.id
                    break
            
            # Also update the transaction
            transaction.matched_move_id = move.id
            
        except Exception as e:
            raise UserError(_('Error creating journal entry: %s') % str(e))

    def action_preview_matching(self):
        """Preview the matching before reconciling"""
        self.ensure_one()
        if not self.selected_line_ids:
            raise UserError(_('Please select at least one accounting entry.'))
        
        total_debit = sum(line.debit for line in self.selected_line_ids)
        total_credit = sum(line.credit for line in self.selected_line_ids)
        total_net = total_debit - total_credit
        
        message = _(
            "Selected Entries Summary:\n"
            "Total Debit: %s\n"
            "Total Credit: %s\n"
            "Net Amount: %s\n\n"
        ) % (total_debit, total_credit, total_net)
        
        if self.transaction_id:
            message += _(
                "Transaction Details:\n"
                "Description: %s\n"
                "Debit: %s\n"
                "Credit: %s\n"
                "Net: %s\n"
            ) % (
                self.transaction_id.description,
                self.transaction_id.debit or 0.0,
                self.transaction_id.credit or 0.0,
                self.transaction_id.amount
            )
        
        if self.match_type == 'debit_credit':
            if self.transaction_id:
                debit_match = abs(total_debit - self.transaction_id.debit) < 0.01
                credit_match = abs(total_credit - self.transaction_id.credit) < 0.01
                
                if debit_match and credit_match:
                    message += _("\n✓ Debit and Credit amounts match perfectly!")
                else:
                    message += _("\n⚠ Debit/Credit amounts do not match!")
                    if not debit_match:
                        message += _("\n  Debit mismatch: Selected %s vs Transaction %s") % (
                            total_debit, self.transaction_id.debit
                        )
                    if not credit_match:
                        message += _("\n  Credit mismatch: Selected %s vs Transaction %s") % (
                            total_credit, self.transaction_id.credit
                        )
        else:
            if self.transaction_id:
                trans_amount = abs(self.transaction_id.amount)
                selected_amount = abs(total_net)
                
                if abs(trans_amount - selected_amount) < 0.01:
                    message += _("\n✓ Net amounts match perfectly!")
                else:
                    message += _("\n⚠ Net amount mismatch: Selected %s vs Transaction %s") % (
                        selected_amount, trans_amount
                    )
        
        # Add journal entry info if enabled
        if self.create_journal_entry:
            journal = self.journal_id or self.master_id.journal_id
            message += _("\n\nJournal Entry will be created in: %s") % (journal.display_name if journal else 'Not selected')
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'reconcile.preview.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_message': message,
                'default_total_debit': total_debit,
                'default_total_credit': total_credit,
                'default_total_net': total_net,
                'default_line_count': len(self.selected_line_ids),
            }
        }

    @api.onchange('match_type')
    def _onchange_match_type(self):
        """Refresh unreconciled lines when match type changes"""
        self._compute_unreconciled_lines()
    
    @api.onchange('master_id')
    def _onchange_master_id(self):
        """Set default journal from master"""
        if self.master_id and self.master_id.journal_id:
            self.journal_id = self.master_id.journal_id.id