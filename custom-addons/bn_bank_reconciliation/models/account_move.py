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
    bank_reconciliation_original_move_ids = fields.Many2many(
        'account.move',
        string='Original Entries',
        compute='_compute_bank_reconciliation_original_moves',
        help='Entries whose bank statement lines this reconciliation entry moves to the Posted Account'
    )
    bank_reconciliation_original_move_id = fields.Many2one(
        'account.move',
        string='Original Entry',
        compute='_compute_bank_reconciliation_original_moves'
    )
    bank_reconciliation_original_count = fields.Integer(
        compute='_compute_bank_reconciliation_original_moves'
    )

    def _compute_bank_reconciliation_original_moves(self):
        ids = [id_ for id_ in self.ids if isinstance(id_, int)]
        # Unreconciled lines are archived but still name their (cancelled) entry
        reconciled = self.env['bank.reconciliation.reconciled'].with_context(active_test=False).search([
            ('reconciliation_move_id', 'in', ids),
        ])
        masters = self.env['bank.reconciliation.master'].search([('move_id', 'in', ids)])
        for move in self:
            originals = reconciled.filtered(lambda r: r.reconciliation_move_id == move).mapped('matched_move_id')
            # Reconciliations validated before the entries were made per line have
            # one entry for all their lines
            for master in masters.filtered(lambda m: m.move_id == move):
                originals |= master.reconciled_ids.filtered(
                    lambda r: r.matched_move_line_id.account_id != master.posted_account_id
                ).mapped('matched_move_id')
            move.bank_reconciliation_original_move_ids = originals
            move.bank_reconciliation_original_move_id = originals if len(originals) == 1 else False
            move.bank_reconciliation_original_count = len(originals)

    def action_view_bank_reconciliation_original_moves(self):
        self.ensure_one()
        originals = self.bank_reconciliation_original_move_ids
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'name': _('Original Entries'),
            'target': 'current',
        }
        if len(originals) == 1:
            action.update({'view_mode': 'form', 'res_id': originals.id})
        else:
            action.update({'view_mode': 'tree,form', 'domain': [('id', 'in', originals.ids)]})
        return action

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
