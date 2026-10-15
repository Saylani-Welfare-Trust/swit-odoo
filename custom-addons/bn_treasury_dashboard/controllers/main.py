from odoo import http
from odoo.http import request

class TreasuryDashboardController(http.Controller):

    @http.route('/treasury/dashboard/data', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_data(self, **kwargs):
        # 1. Calculate Total Cash & Bank Balance
        liquidity_journals = request.env['account.journal'].search([('type', 'in', ['bank', 'cash'])])
        total_cash = sum(liquidity_journals.mapped('current_balance'))

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
        # Using read_group for efficient database aggregation
        domain = [
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
            ('parent_state', '=', 'posted'),
            ('date', '>=', '2024-01-01'), # Adjust dynamically as needed
        ]
        
        # Group by month and account type
        grouped_data = request.env['account.move.line'].read_group(
            domain,
            ['amount_residual:sum'],
            ['date:month', 'account_id.account_type'],
            lazy=False
        )

        # Format data for Chart.js
        months = []
        receivable_data = []
        payable_data = []
        
        # Initialize dictionary to hold monthly totals
        monthly_totals = {}
        
        for group in grouped_data:
            month_str = group['date:month'] # e.g., "January 2024"
            account_type = group['account_id.account_type']
            amount = group['amount_residual']
            
            if month_str not in monthly_totals:
                monthly_totals[month_str] = {'receivable': 0.0, 'payable': 0.0}
                months.append(month_str)
                
            if account_type == 'asset_receivable':
                monthly_totals[month_str]['receivable'] += amount
            elif account_type == 'liability_payable':
                monthly_totals[month_str]['payable'] += amount

        # Build final arrays matching the months array order
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