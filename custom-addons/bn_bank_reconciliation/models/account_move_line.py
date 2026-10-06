from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    is_bank_reconciled = fields.Boolean(
        string='Bank Reconciled',
        help='Indicates if this line has been bank reconciled',
        default=False
    )
    bank_reconciliation_id = fields.Many2one(
        'bank.reconciliation.master',
        string='Bank Reconciliation'
    )
    bank_reconciliation_date = fields.Date(
        string='Bank Reconciliation Date'
    )
    bank_reconciliation_transaction_id = fields.Many2one(
        'bank.reconciliation.transaction',
        string='Bank Statement Line',
        index='btree_not_null',
        help='Bank statement line this journal item has been reconciled with'
    )