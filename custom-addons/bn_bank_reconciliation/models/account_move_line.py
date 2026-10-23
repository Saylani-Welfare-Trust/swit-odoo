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