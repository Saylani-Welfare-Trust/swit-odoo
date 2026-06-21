from odoo import fields, models, _
from odoo.exceptions import UserError


class BankReconciliationReconciled(models.Model):
    _name = 'bank.reconciliation.reconciled'
    _description = 'Bank Reconciliation Reconciled Transaction'
    _order = 'reconciliation_date desc, id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    master_id = fields.Many2one(
        'bank.reconciliation.master',
        string='Reconciliation Master',
        required=True,
        ondelete='cascade'
    )
    transaction_id = fields.Many2one(
        'bank.reconciliation.transaction',
        string='Original Transaction',
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
    amount = fields.Monetary(
        string='Amount',
        required=True,
        currency_field='currency_id'
    )
    reference = fields.Char(
        string='Reference'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner'
    )

    account_id = fields.Many2one(
        'account.account',
        string='Account',
        required=True
    )
    matched_move_id = fields.Many2one(
        'account.move',
        string='Reconciled Entry'
    )
    matched_move_line_id = fields.Many2one(
        'account.move.line',
        string='Reconciled Journal Item'
    )
    confidence_level = fields.Selection([
        ('high', 'High Match'),
        ('medium', 'Medium Match'),
        ('low', 'Low Match')
    ], string='Confidence Level')

    reconciled_by = fields.Many2one(
        'res.users',
        string='Reconciled By',
        required=True,
        default=lambda self: self.env.user
    )
    reconciliation_date = fields.Datetime(
        string='Reconciliation Date',
        required=True,
        default=fields.Datetime.now
    )

    notes = fields.Text(string='Notes')
    adjustment_type = fields.Selection([
        ('bank_charge', 'Bank Charge'),
        ('withholding_tax', 'Withholding Tax'),
        ('interest_income', 'Interest Income'),
        ('miscellaneous', 'Miscellaneous Expense'),
        ('transfer', 'Bank Transfer')
    ], string='Adjustment Type')

    _sql_constraints = [
        ('unique_reconciled_transaction', 'unique(transaction_id)',
         'This transaction is already reconciled.')
    ]

    def action_view_move(self):
        self.ensure_one()
        if not self.matched_move_id:
            raise UserError(_('No accounting entry found for this reconciliation.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.matched_move_id.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def action_unreconcile(self):
        self.ensure_one()
        if self.master_id.state == 'completed':
            raise UserError(_('Cannot unreconcile from a completed reconciliation.'))
        if self.transaction_id:
            self.transaction_id.write({
                'state': 'matched',
                'reconciled': False,
                'reconciled_date': False,
                'reconciled_by': False
            })
        self.unlink()
        return True