from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_bank_reconciled = fields.Boolean(
        string='Bank Reconciled',
        help='Indicates if this move has been bank reconciled',
        compute='_compute_bank_reconciliation',
        search='_search_is_bank_reconciled'
    )
    bank_reconciliation_id = fields.Many2one(
        'bank.reconciliation.master',
        string='Bank Reconciliation',
        compute='_compute_bank_reconciliation'
    )
    bank_reconciliation_ids = fields.Many2many(
        'bank.reconciliation.master',
        string='Bank Reconciliations'
    )
    bank_reconciliation_created_id = fields.Many2one(
        'bank.reconciliation.master',
        string='Created by Bank Reconciliation',
        readonly=True,
        copy=False,
        index='btree_not_null',
        help='Bank reconciliation that created this entry for statement lines with no entry in Odoo'
    )

    @api.depends('line_ids.is_bank_reconciled', 'line_ids.bank_reconciliation_id')
    def _compute_bank_reconciliation(self):
        # Reconciling a statement line flags the journal items of the entry
        for move in self:
            reconciled_lines = move.line_ids.filtered('is_bank_reconciled')
            move.is_bank_reconciled = bool(reconciled_lines)
            move.bank_reconciliation_id = reconciled_lines.mapped('bank_reconciliation_id')[:1]

    def _search_is_bank_reconciled(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise UserError(_('Operation not supported'))
        reconciled_lines = [('bank_reconciliation_id', '!=', False)]
        if (operator == '=') == value:
            return [('line_ids', 'any', reconciled_lines)]
        return [('line_ids', 'not any', reconciled_lines)]
