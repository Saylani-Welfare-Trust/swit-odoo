from odoo import http
from odoo.http import request
from datetime import date

class TreasuryDashboardController(http.Controller):

    @http.route('/treasury/dashboard/data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_data(self, **kwargs):
        # 1. Calculate Total Cash & Bank Balance
        # FIX: In Odoo 17, 'current_balance' is on 'account.account', not 'account.journal'
        liquidity_accounts = request.env['account.account'].search([('account_type', '=', 'asset_cash')])
        total_cash = sum(liquidity_accounts.mapped('current_balance'))

        # 2. Calculate Total Receivables (Outstanding Customer Invoices)
        receivables = request.env['account.move.line'].search([
            ('account_id.account_type', '=', 'asset_receivable'),
            ('amount_residual', '>', 0),
            ('parent_state', '=', 'posted')
        ])
        total_receivables = sum(receivables.mapped('amount_residual'))

        # 3. Calculate Total Payables (Outstanding Vendor Bills)
        payables = request.env['account.move.line'].search([
            ('account_id.account_type', '=', 'liability_payable'),
            ('amount_residual', '>', 0),
            ('parent_state', '=', 'posted')
        ])
        total_payables = sum(payables.mapped('amount_residual'))

        # 4. Chart Data: Payables vs Receivables grouped by Month (Current Year)
        # FIX: Made the date dynamic instead of hardcoding 2024-01-01
        start_of_year = date.today().replace(month=1, day=1).strftime('%Y-%m-%d')
        
        domain = [
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
            ('parent_state', '=', 'posted'),
            ('date', '>=', start_of_year),
        ]
        
        grouped_data = request.env['account.move.line'].read_group(
            domain,
            ['amount_residual:sum'],
            ['date:month', 'account_id.account_type'],
            lazy=False
        )

        months = []
        receivable_data = []
        payable_data = []
        monthly_totals = {}
        
        for group in grouped_data:
            month_str = group['date:month'] 
            account_type = group['account_id.account_type']
            amount = group['amount_residual']
            
            if month_str not in monthly_totals:
                monthly_totals[month_str] = {'receivable': 0.0, 'payable': 0.0}
                months.append(month_str)
                
            if account_type == 'asset_receivable':
                monthly_totals[month_str]['receivable'] += amount
            elif account_type == 'liability_payable':
                monthly_totals[month_str]['payable'] += amount

        # Ensure data aligns with the months array
        for month in months:
            receivable_data.append(monthly_totals[month]['receivable'])
            payable_data.append(monthly_totals[month]['payable'])

        return {
            'kpis': {
                'total_cash': total_cash,
                'total_receivables': total_receivables,
                'total_payables': total_payables,
            },
            'chart': {
                'labels': months,
                'receivables': receivable_data,
                'payables': payable_data,
            }
        }