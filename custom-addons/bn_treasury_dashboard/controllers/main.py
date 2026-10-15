from odoo import http
from odoo.http import request
from datetime import date

class TreasuryDashboardController(http.Controller):

    @http.route('/treasury/dashboard/data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_data(self, **kwargs):
        # 1. Calculate Total Cash & Bank Balance
        liquidity_accounts = request.env['account.account'].search([('account_type', '=', 'asset_cash')])
        total_cash = sum(liquidity_accounts.mapped('current_balance'))

        # 2. Calculate Total Receivables
        receivables = request.env['account.move.line'].search([
            ('account_id.account_type', '=', 'asset_receivable'),
            ('amount_residual', '>', 0),
            ('parent_state', '=', 'posted')
        ])
        total_receivables = sum(receivables.mapped('amount_residual'))

        # 3. Calculate Total Payables
        payables = request.env['account.move.line'].search([
            ('account_id.account_type', '=', 'liability_payable'),
            ('amount_residual', '>', 0),
            ('parent_state', '=', 'posted')
        ])
        total_payables = sum(payables.mapped('amount_residual'))

        # 4. Chart Data: Payables vs Receivables grouped by Month (Current Year)
        start_of_year = date.today().replace(month=1, day=1).strftime('%Y-%m-%d')

        # FIX: Split into two separate read_group calls to avoid nested field grouping error
        # Receivables grouped by month
        receivable_groups = request.env['account.move.line'].read_group(
            [
                ('account_id.account_type', '=', 'asset_receivable'),
                ('parent_state', '=', 'posted'),
                ('date', '>=', start_of_year),
            ],
            ['amount_residual:sum'],
            ['date:month'],
            lazy=False
        )

        # Payables grouped by month
        payable_groups = request.env['account.move.line'].read_group(
            [
                ('account_id.account_type', '=', 'liability_payable'),
                ('parent_state', '=', 'posted'),
                ('date', '>=', start_of_year),
            ],
            ['amount_residual:sum'],
            ['date:month'],
            lazy=False
        )

        # Build a unified month list (sorted chronologically)
        all_months = set()
        receivable_map = {}
        payable_map = {}

        for group in receivable_groups:
            month_str = group['date:month']
            all_months.add(month_str)
            receivable_map[month_str] = group['amount_residual']

        for group in payable_groups:
            month_str = group['date:month']
            all_months.add(month_str)
            payable_map[month_str] = group['amount_residual']

        # Sort months (e.g., "January 2025", "February 2025" ...)
        # Odoo returns month format like "January 2025", so we sort using datetime
        from datetime import datetime
        def month_sort_key(m):
            try:
                return datetime.strptime(m, "%B %Y")
            except ValueError:
                return datetime.min

        sorted_months = sorted(all_months, key=month_sort_key)

        receivable_data = [receivable_map.get(m, 0.0) for m in sorted_months]
        payable_data = [payable_map.get(m, 0.0) for m in sorted_months]

        return {
            'kpis': {
                'total_cash': total_cash,
                'total_receivables': total_receivables,
                'total_payables': total_payables,
            },
            'chart': {
                'labels': sorted_months,
                'receivables': receivable_data,
                'payables': payable_data,
            }
        }