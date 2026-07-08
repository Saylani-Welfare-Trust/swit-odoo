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
    
    match_type = fields.Selection([
        ('net', 'Match Net Amount'),
        ('debit_credit', 'Match Debit/Credit Separately'),
        ('intelligent', 'Intelligent Match')
    ], string='Match Type', default='intelligent')
    
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
    
    match_threshold = fields.Integer(
        string='Match Threshold',
        default=40,
        help='Minimum score to consider a match (0-100)'
    )
    
    view_mode = fields.Selection([
        ('simple', 'Simple View'),
        ('detailed', 'Detailed View')
    ], string='View Mode', default='detailed')

    @api.depends('account_id', 'date_from', 'date_to', 'partner_id', 'transaction_id', 'match_type')
    def _compute_unreconciled_lines(self):
        for wizard in self:
            domain = [
                ('account_id', '=', wizard.account_id.id),
                ('is_bank_reconciled', '=', False),  # Exclude already reconciled lines
                ('reconciled', '=', False),  # Exclude already reconciled lines
                ('company_id', '=', wizard.master_id.company_id.id)
            ]
            if wizard.date_from:
                domain.append(('date', '>=', wizard.date_from))
            if wizard.date_to:
                domain.append(('date', '<=', wizard.date_to))
            if wizard.partner_id:
                domain.append(('partner_id', '=', wizard.partner_id.id))
            
            # Also exclude lines already linked to reconciled records
            reconciled_line_ids = self.env['bank.reconciliation.reconciled'].search([
                ('matched_move_line_id', '!=', False)
            ]).mapped('matched_move_line_id.id')
            
            if reconciled_line_ids:
                domain.append(('id', 'not in', reconciled_line_ids))
            
            lines = self.env['account.move.line'].search(domain)
            
            if wizard.show_only_matching_amount and wizard.transaction_id:
                matching_lines = self.env['account.move.line']
                
                if wizard.match_type == 'intelligent':
                    matches = wizard.transaction_id._find_matching_move_lines()
                    for match in matches:
                        if match['score'] >= wizard.match_threshold:
                            matching_lines |= match['move_line']
                
                elif wizard.match_type == 'debit_credit':
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
            
            if not wizard.journal_id and wizard.master_id:
                wizard.journal_id = wizard.master_id.journal_id.id

    def action_reconcile(self):
        self.ensure_one()
        if not self.selected_line_ids:
            raise UserError(_('Please select at least one accounting entry to reconcile.'))
        
        if not self.transaction_id:
            return self._reconcile_multiple_transactions()
        
        if self.transaction_id.state == 'reconciled':
            raise UserError(_('This transaction is already reconciled.'))
        
        existing = self.env['bank.reconciliation.reconciled'].search([
            ('transaction_id', '=', self.transaction_id.id)
        ], limit=1)
        if existing:
            raise UserError(_(
                'This transaction already has a reconciled record. Cannot reconcile again.'
            ))
        
        return self._reconcile_single_transaction()

    def _reconcile_single_transaction(self):
        self.ensure_one()
        transaction = self.transaction_id
        
        if transaction.state == 'reconciled':
            raise UserError(_('This transaction is already reconciled.'))
        
        if self.env['bank.reconciliation.reconciled'].search_count([('transaction_id', '=', transaction.id)]) > 0:
            raise UserError(_('This transaction already has a reconciled record. Cannot reconcile again.'))
        
        if not self._validate_selected_lines(transaction):
            return False
        
        for line in self.selected_line_ids:
            line.write({
                'is_bank_reconciled': True,
                'bank_reconciliation_id': self.master_id.id,
                'bank_reconciliation_date': fields.Date.today()
            })
        
        first_line = self.selected_line_ids[0] if self.selected_line_ids else False
        
        match_data = {
            'move_line': first_line,
            'move': first_line.move_id if first_line else False,
        }
        
        transaction._apply_match(match_data, manual=True)
        
        if self.env['bank.reconciliation.reconciled'].search_count([('transaction_id', '=', transaction.id)]) > 0:
            raise UserError(_('This transaction already has a reconciled record. Cannot reconcile again.'))
        
        transaction.action_accept_match()
        
        if self.create_journal_entry:
            reconciled = self.env['bank.reconciliation.reconciled'].search([
                ('transaction_id', '=', transaction.id)
            ], limit=1)
            if reconciled and not reconciled.is_posted:
                self._create_journal_entry_for_reconciliation(transaction, reconciled)

    def _validate_selected_lines(self, transaction):
        self.ensure_one()
        
        if self.match_type == 'intelligent':
            return True
            
        elif self.match_type == 'debit_credit':
            total_debit = sum(line.debit for line in self.selected_line_ids)
            total_credit = sum(line.credit for line in self.selected_line_ids)
            
            if transaction.debit and abs(transaction.debit - total_debit) > 0.01:
                raise UserError(_(
                    'Total debit amount (%s) does not match transaction debit (%s).'
                ) % (total_debit, transaction.debit))
            
            if transaction.credit and abs(transaction.credit - total_credit) > 0.01:
                raise UserError(_(
                    'Total credit amount (%s) does not match transaction credit (%s).'
                ) % (total_credit, transaction.credit))
        else:
            total_selected = sum(abs(line.balance) for line in self.selected_line_ids)
            transaction_amount = abs(transaction.amount)
            
            if abs(total_selected - transaction_amount) > 0.01:
                raise UserError(_(
                    'Total selected amount (%s) does not match transaction amount (%s).'
                ) % (total_selected, transaction_amount))
        
        return True

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
        
        if self.match_type == 'intelligent':
            for trans in unmatched_trans:
                if trans.state == 'reconciled':
                    continue
                if self.env['bank.reconciliation.reconciled'].search_count([('transaction_id', '=', trans.id)]) > 0:
                    continue
                matches = trans._find_matching_move_lines()
                for match in matches:
                    if match['move_line'].id in self.selected_line_ids.ids:
                        if match['score'] >= self.match_threshold:
                            matching_trans |= trans
                            break
        
        elif self.match_type == 'debit_credit':
            for trans in unmatched_trans:
                if trans.state == 'reconciled':
                    continue
                if self.env['bank.reconciliation.reconciled'].search_count([('transaction_id', '=', trans.id)]) > 0:
                    continue
                if abs(trans.debit - total_selected_debit) < 0.01 and abs(trans.credit - total_selected_credit) < 0.01:
                    matching_trans |= trans
        else:
            for trans in unmatched_trans:
                if trans.state == 'reconciled':
                    continue
                if self.env['bank.reconciliation.reconciled'].search_count([('transaction_id', '=', trans.id)]) > 0:
                    continue
                if abs(abs(trans.amount) - total_selected_amount) < 0.01:
                    matching_trans |= trans
        
        if not matching_trans:
            raise UserError(_('No unmatched transaction found matching the selected entries.'))
        
        for trans in matching_trans:
            if trans.state == 'reconciled':
                continue
            if self.env['bank.reconciliation.reconciled'].search_count([('transaction_id', '=', trans.id)]) > 0:
                continue
            
            matching_lines = self.env['account.move.line']
            
            if self.match_type == 'intelligent':
                matches = trans._find_matching_move_lines()
                for match in matches:
                    if match['move_line'].id in self.selected_line_ids.ids:
                        matching_lines |= match['move_line']
            else:
                matching_lines = self.selected_line_ids
            
            if matching_lines:
                self._reconcile_transaction_with_lines(trans, matching_lines)

    def _reconcile_transaction_with_lines(self, transaction, lines):
        if transaction.state == 'reconciled':
            return
        
        if self.env['bank.reconciliation.reconciled'].search_count([('transaction_id', '=', transaction.id)]) > 0:
            return
        
        for line in lines:
            line.write({
                'is_bank_reconciled': True,
                'bank_reconciliation_id': self.master_id.id,
                'bank_reconciliation_date': fields.Date.today()
            })
        
        first_line = lines[0] if lines else False
        
        match_data = {
            'move_line': first_line,
            'move': first_line.move_id if first_line else False,
        }
        
        transaction._apply_match(match_data, manual=True)
        
        if self.env['bank.reconciliation.reconciled'].search_count([('transaction_id', '=', transaction.id)]) > 0:
            return
        
        transaction.action_accept_match()
        
        if self.create_journal_entry:
            reconciled = self.env['bank.reconciliation.reconciled'].search([
                ('transaction_id', '=', transaction.id)
            ], limit=1)
            if reconciled and not reconciled.is_posted:
                self._create_journal_entry_for_reconciliation(transaction, reconciled)

    def _create_journal_entry_for_reconciliation(self, transaction, reconciled):
        self.ensure_one()
        if not reconciled:
            return
        if reconciled.is_posted:
            return
        if reconciled.matched_move_id:
            return
        
        journal = self.journal_id or self.master_id.journal_id
        if not journal:
            raise UserError(_('Please select a journal for the journal entry.'))
        
        move_lines = []
        
        if reconciled.debit > 0:
            move_lines.append((0, 0, {
                'account_id': reconciled.account_id.id,
                'partner_id': reconciled.partner_id.id if reconciled.partner_id else False,
                'debit': reconciled.debit,
                'credit': 0.0,
                'name': _('%s - %s') % (transaction.master_id.name, transaction.description[:50]),
                'date': transaction.date or fields.Date.today(),
                'is_bank_reconciled': True,
                'bank_reconciliation_id': transaction.master_id.id,
                'bank_reconciliation_date': transaction.date,
            }))
            move_lines.append((0, 0, {
                'account_id': transaction.master_id.posted_account_id.id,
                'partner_id': reconciled.partner_id.id if reconciled.partner_id else False,
                'debit': 0.0,
                'credit': reconciled.debit,
                'name': _('Contra: %s') % transaction.master_id.posted_account_id.name,
                'date': transaction.date or fields.Date.today(),
                'is_bank_reconciled': True,
                'bank_reconciliation_id': transaction.master_id.id,
                'bank_reconciliation_date': transaction.date,
            }))
        
        if reconciled.credit > 0:
            move_lines.append((0, 0, {
                'account_id': reconciled.account_id.id,
                'partner_id': reconciled.partner_id.id if reconciled.partner_id else False,
                'debit': 0.0,
                'credit': reconciled.credit,
                'name': _('%s - %s') % (transaction.master_id.name, transaction.description[:50]),
                'date': transaction.date or fields.Date.today(),
                'is_bank_reconciled': True,
                'bank_reconciliation_id': transaction.master_id.id,
                'bank_reconciliation_date': transaction.date,
            }))
            move_lines.append((0, 0, {
                'account_id': transaction.master_id.posted_account_id.id,
                'partner_id': reconciled.partner_id.id if reconciled.partner_id else False,
                'debit': reconciled.credit,
                'credit': 0.0,
                'name': _('Contra: %s') % transaction.master_id.posted_account_id.name,
                'date': transaction.date or fields.Date.today(),
                'is_bank_reconciled': True,
                'bank_reconciliation_id': transaction.master_id.id,
                'bank_reconciliation_date': transaction.date,
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
                'date': transaction.date or fields.Date.today(),
                'ref': '%s - %s' % (transaction.master_id.name, transaction.reference or transaction.id),
                'company_id': transaction.master_id.company_id.id,
                'line_ids': move_lines,
                'narration': _('Bank Reconciliation: %s - Transaction: %s') % (
                    transaction.master_id.name, transaction.description[:100]
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
            
            transaction.matched_move_id = move.id
            
        except Exception as e:
            raise UserError(_('Error creating journal entry: %s') % str(e))

    def action_preview_matching(self):
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
            
            if hasattr(self.transaction_id, 'matched_move_line_id') and self.transaction_id.matched_move_line_id:
                message += _("\nCurrently matched to: %s") % self.transaction_id.matched_move_line_id.display_name
        
        if self.match_type == 'intelligent':
            matches = self.transaction_id._find_matching_move_lines() if self.transaction_id else []
            if matches:
                message += _("\n\nIntelligent Matching Results:\n")
                for i, match in enumerate(matches[:5], 1):
                    message += _(
                        "%d. %s (Score: %s)\n"
                        "   Match Criteria: %s\n"
                    ) % (
                        i,
                        match['move_line'].display_name or match['move_line'].name,
                        match['score'],
                        ', '.join(match['criteria'].keys()) if match['criteria'] else 'None'
                    )
        
        elif self.match_type == 'debit_credit':
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

    def action_show_match_details(self):
        self.ensure_one()
        if not self.selected_line_ids:
            raise UserError(_('Please select at least one accounting entry.'))
        
        details = []
        for line in self.selected_line_ids:
            details.append(_(
                "Line: %s\n"
                "Account: %s\n"
                "Debit: %s\n"
                "Credit: %s\n"
                "Balance: %s\n"
                "Date: %s\n"
                "Partner: %s\n"
                "Reference: %s\n"
                "---\n"
            ) % (
                line.display_name or line.name,
                line.account_id.display_name,
                line.debit or 0.0,
                line.credit or 0.0,
                line.balance,
                line.date,
                line.partner_id.display_name if line.partner_id else '',
                line.move_id.ref or '',
            ))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'reconcile.preview.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_message': '\n'.join(details),
                'default_total_debit': sum(line.debit for line in self.selected_line_ids),
                'default_total_credit': sum(line.credit for line in self.selected_line_ids),
                'default_total_net': sum(line.debit for line in self.selected_line_ids) - sum(line.credit for line in self.selected_line_ids),
                'default_line_count': len(self.selected_line_ids),
            }
        }

    def action_clear_selection(self):
        self.ensure_one()
        self.selected_line_ids = [(5, 0, 0)]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'reconcile.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.onchange('match_type')
    def _onchange_match_type(self):
        self._compute_unreconciled_lines()
    
    @api.onchange('master_id')
    def _onchange_master_id(self):
        if self.master_id and self.master_id.journal_id:
            self.journal_id = self.master_id.journal_id.id


class ReconcilePreviewWizard(models.TransientModel):
    _name = 'reconcile.preview.wizard'
    _description = 'Reconciliation Preview'

    message = fields.Text(string='Preview Message', readonly=True)
    total_debit = fields.Float(string='Total Debit', readonly=True)
    total_credit = fields.Float(string='Total Credit', readonly=True)
    total_net = fields.Float(string='Net Amount', readonly=True)
    line_count = fields.Integer(string='Number of Lines', readonly=True)

    def action_confirm(self):
        return {'type': 'ir.actions.act_window_close'}