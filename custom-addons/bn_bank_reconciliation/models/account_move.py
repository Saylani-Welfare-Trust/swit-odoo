from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_bank_reconciled = fields.Boolean(
        string='Bank Reconciled',
        help='Indicates if this move has been bank reconciled',
        default=False
    )
    bank_reconciliation_ids = fields.Many2many(
        'bank.reconciliation.master',
        string='Bank Reconciliations'
    )