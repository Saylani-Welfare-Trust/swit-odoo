from odoo import fields, models, _

class ShariahLaw(models.Model):
    _name = 'shariah.law'
    _description = "Shariah Law Aggregated Totals"
    _rec_name = 'analytic_account_id'

    parent_id = fields.Many2one('account.analytic.account', string="Parent Analytic Account")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", required=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)

    # Cumulative totals (from the start)
    inflow_restricted_amount = fields.Monetary('Inflow (Restricted)', currency_field='currency_id', default=0)
    inflow_unrestricted_amount = fields.Monetary('Inflow (Unrestricted)', currency_field='currency_id', default=0)
    purchase_amount = fields.Monetary('Purchase', currency_field='currency_id', default=0)
    expense_amount = fields.Monetary('Expense', currency_field='currency_id', default=0)
    welfare_individual_amount = fields.Monetary('Welfare (Individual)', currency_field='currency_id', default=0)
    welfare_portal_amount = fields.Monetary('Welfare (Portal)', currency_field='currency_id', default=0)

    # Opening and Closing balances (computed from daily records)
    opening_balance = fields.Monetary(
        string='Opening Balance',
        currency_field='currency_id',
        compute='_compute_balances_from_daily',
        store=False
    )
    closing_balance = fields.Monetary(
        string='Closing Balance',
        currency_field='currency_id',
        compute='_compute_balances_from_daily',
        store=False
    )

    def _compute_balances_from_daily(self):
        """Fetch today's opening and closing from the daily balance model."""
        today = fields.Date.context_today(self)
        for rec in self:
            daily = self.env['shariah.daily.balance'].search([
                ('analytic_account_id', '=', rec.analytic_account_id.id),
                ('date', '=', today)
            ], limit=1)
            if daily:
                rec.opening_balance = daily.opening_balance
                rec.closing_balance = daily.closing_balance
            else:
                rec.opening_balance = 0.0
                rec.closing_balance = 0.0

    def action_transfer_to(self):
        """Open transfer wizard with this account as source."""
        return {
            'name': _('Transfer To'),
            'type': 'ir.actions.act_window',
            'res_model': 'shariah.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_source_analytic_account_id': self.analytic_account_id.id,
            }
        }

    def action_transfer_from(self):
        """Open transfer wizard with this account as destination."""
        return {
            'name': _('Transfer From'),
            'type': 'ir.actions.act_window',
            'res_model': 'shariah.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_destination_analytic_account_id': self.analytic_account_id.id,
            }
        }