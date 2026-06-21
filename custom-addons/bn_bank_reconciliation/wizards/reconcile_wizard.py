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

    @api.depends('account_id', 'date_from', 'date_to', 'partner_id', 'transaction_id')
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
            if wizard.show_only_matching_amount and wizard.transaction_id:
                transaction_amount = abs(wizard.transaction_id.amount)
                lines = self.env['account.move.line'].search(domain)
                matching_lines = lines.filtered(
                    lambda l: abs(abs(l.balance) - transaction_amount) < 1.0
                )
                wizard.unreconciled_line_ids = matching_lines
            else:
                wizard.unreconciled_line_ids = self.env['account.move.line'].search(domain)

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
        total_selected = sum(abs(line.balance) for line in self.selected_line_ids)
        if abs(abs(transaction.amount) - total_selected) > 0.01:
            raise UserError(_(
                'Total selected amount (%s) does not match transaction amount (%s). '
                'Please select entries that sum to the transaction amount.'
            ) % (total_selected, abs(transaction.amount)))
        for line in self.selected_line_ids:
            line.write({
                'is_bank_reconciled': True,
                'bank_reconciliation_id': self.master_id.id,
                'bank_reconciliation_date': fields.Date.today()
            })
        transaction.write({
            'state': 'reconciled',
            'reconciled': True,
            'reconciled_date': fields.Datetime.now(),
            'reconciled_by': self.env.user
        })
        transaction._create_reconciled_record()
        return {'type': 'ir.actions.act_window_close'}

    def _reconcile_multiple_transactions(self):
        self.ensure_one()
        # For each unmatched transaction of the master, try to match with selected lines
        # Find all unmatched transactions that don't have an account? Actually we use the master's unmatched transactions
        # We'll reconcile all transactions that have the same account as the wizard's account
        # and have amount matching the sum of selected lines? This is complex; a simpler approach:
        # For bulk, we just allow selecting multiple lines and reconcile them against one transaction?
        # Better: we can allow selecting multiple lines and then assign them to multiple transactions?
        # Per document: "display all unmatched bank transactions and all unreconciled accounting entries, user can perform bulk reconciliations"
        # We'll implement a simple approach: the user selects multiple accounting entries, and we try to match them with the first unmatched transaction that matches the total.
        # But a more practical approach: we allow the user to manually assign selected lines to a specific transaction (by choosing which transaction).
        # For simplicity, we'll let the user select multiple lines and then we'll try to find an unmatched transaction with the same total.
        # However, the wizard is called from master with a specific account, so we'll list all unmatched transactions for that account.
        # The user can then pick one transaction to reconcile with the selected lines, or we can automatically match if total matches.
        # I'll implement a simple: if total selected amount equals total of one unmatched transaction, reconcile that transaction.

        # For bulk, we should have a tree view of transactions and lines to pair.
        # To keep it simple, we'll check if the total selected amount matches any single unmatched transaction.
        total_selected = sum(abs(line.balance) for line in self.selected_line_ids)
        unmatched_trans = self.master_id.transaction_ids.filtered(
            lambda t: t.state in ['matched', 'unmatched'] and t.account_id == self.account_id
        )
        matching_trans = unmatched_trans.filtered(
            lambda t: abs(abs(t.amount) - total_selected) < 0.01
        )
        if not matching_trans:
            raise UserError(_(
                'No unmatched transaction found with amount matching the selected entries total (%s).'
            ) % total_selected)
        # Take the first matching transaction
        trans = matching_trans[0]
        # Now reconcile this transaction with the selected lines
        for line in self.selected_line_ids:
            line.write({
                'is_bank_reconciled': True,
                'bank_reconciliation_id': self.master_id.id,
                'bank_reconciliation_date': fields.Date.today()
            })
        trans.write({
            'state': 'reconciled',
            'reconciled': True,
            'reconciled_date': fields.Datetime.now(),
            'reconciled_by': self.env.user,
            'matched_move_id': self.selected_line_ids[0].move_id.id,  # just for reference
        })
        trans._create_reconciled_record()
        # After reconciling, close wizard
        return {'type': 'ir.actions.act_window_close'}