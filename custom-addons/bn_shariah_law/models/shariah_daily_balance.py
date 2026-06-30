from odoo import api, fields, models, _

class ShariahDailyBalance(models.Model):
    _name = 'shariah.daily.balance'
    _description = 'Shariah Daily Balance'
    _order = 'date desc, analytic_account_id'
    _rec_name = 'analytic_account_id'

    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', required=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    currency_id = fields.Many2one('res.currency', string='Currency', related='analytic_account_id.currency_id', readonly=True)

    # Daily movements
    donation_amount = fields.Monetary('Donation', currency_field='currency_id', default=0)
    purchase = fields.Monetary('Purchase', currency_field='currency_id', default=0)
    expense = fields.Monetary('Expense', currency_field='currency_id', default=0)
    transfer_in = fields.Monetary('Transfer In', currency_field='currency_id', default=0)
    transfer_out = fields.Monetary('Transfer Out', currency_field='currency_id', default=0)

    # Computed balances
    opening_balance = fields.Monetary('Opening Balance', currency_field='currency_id', compute='_compute_balances', store=True)
    closing_balance = fields.Monetary('Closing Balance', currency_field='currency_id', compute='_compute_balances', store=True)

    @api.depends('donation_amount', 'purchase', 'expense', 'transfer_in', 'transfer_out', 'date', 'analytic_account_id')
    def _compute_balances(self):
        for rec in self:
            prev = self.search([
                ('analytic_account_id', '=', rec.analytic_account_id.id),
                ('date', '<', rec.date)
            ], order='date desc', limit=1)
            opening = prev.closing_balance if prev else 0.0
            rec.opening_balance = opening
            rec.closing_balance = opening + rec.donation_amount + rec.transfer_in - rec.purchase - rec.expense - rec.transfer_out

    _sql_constraints = [
        ('unique_account_date', 'unique(analytic_account_id, date)', 'Only one balance record per account per day is allowed.')
    ]