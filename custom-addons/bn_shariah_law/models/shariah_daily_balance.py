from odoo import api, fields, models


class ShariahDailyBalance(models.Model):
    _name = 'shariah.daily.balance'
    _description = 'Shariah Daily Balance'
    _order = 'date desc, analytic_account_id'
    _rec_name = 'analytic_account_id'

    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', required=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    currency_id = fields.Many2one('res.currency', string='Currency', related='analytic_account_id.currency_id', readonly=True)

    # Daily movements by source
    # POSITIVE transactions (increase balance)
    pos_donation = fields.Monetary('POS Donation', currency_field='currency_id', default=0)
    api_donation = fields.Monetary('API / Wallet', currency_field='currency_id', default=0)
    dik = fields.Monetary('DIK', currency_field='currency_id', default=0)
    
    # NEGATIVE transactions (decrease balance)
    po = fields.Monetary('PO', currency_field='currency_id', default=0)
    welfare = fields.Monetary('Welfare (Cash)', currency_field='currency_id', default=0)
    microfinance = fields.Monetary('Microfinance (Cash)', currency_field='currency_id', default=0)
    expense = fields.Monetary('Expense', currency_field='currency_id', default=0)
    
    # Transfer movements - unified field (POSITIVE = In, NEGATIVE = Out)
    transfer = fields.Monetary('Transfer', currency_field='currency_id', default=0)

    # Computed fields
    total_donation = fields.Monetary(
        'Total Donation', 
        currency_field='currency_id', 
        compute='_compute_total_donation', 
        store=True
    )
    opening_balance = fields.Monetary(
        'Opening Balance', 
        currency_field='currency_id', 
        compute='_compute_balances', 
        store=True
    )
    closing_balance = fields.Monetary(
        'Closing Balance', 
        currency_field='currency_id', 
        compute='_compute_balances', 
        store=True
    )

    @api.depends('pos_donation', 'api_donation', 'dik')
    def _compute_total_donation(self):
        """Compute total donation from all positive sources."""
        for rec in self:
            rec.total_donation = (
                rec.pos_donation + 
                rec.api_donation + 
                rec.dik
            )

    @api.depends(
        'pos_donation', 'api_donation', 'dik', 'po', 'welfare', 'microfinance', 
        'expense', 'transfer', 'date', 'analytic_account_id'
    )
    def _compute_balances(self):
        """
        Compute opening and closing balances.
        Closing Balance = Opening Balance + Total Donation + Transfer - (PO + Welfare + Microfinance + Expense)
        Note: PO, Welfare, Microfinance, and Expense are already negative values
        """
        for rec in self:
            # Get previous day's closing balance
            prev = self.search([
                ('analytic_account_id', '=', rec.analytic_account_id.id),
                ('date', '<', rec.date)
            ], order='date desc', limit=1)
            
            opening = prev.closing_balance if prev else 0.0
            rec.opening_balance = opening
            
            # Calculate closing balance
            rec.closing_balance = (
                opening + 
                rec.total_donation + 
                rec.transfer + 
                rec.po + 
                rec.welfare + 
                rec.microfinance + 
                rec.expense
            )

    _sql_constraints = [
        ('unique_account_date', 'unique(analytic_account_id, date)', 
         'Only one balance record per account per day is allowed.')
    ]