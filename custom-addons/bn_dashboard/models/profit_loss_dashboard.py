from odoo import models, fields, api
from datetime import datetime

class ProfitLossDashboard(models.TransientModel):
    _name = 'profit.loss.dashboard'
    _description = 'Profit and Loss Dashboard'

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None):
        """ Fetches aggregated data for the P&L Dashboard """
        
        # 1. Date Defaults (This Year)
        if not date_from:
            date_from = f"{fields.Date.today().year}-01-01"
        if not date_to:
            date_to = fields.Date.today().strftime('%Y-%m-%d')

        domain = [
            ('parent_state', '=', 'posted'),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]

        # 2. Fetch Income
        income_domain = domain + [('account_id.account_type', 'in', ('income', 'income_other'))]
        income_lines = self.env['account.move.line'].sudo().read_group(
            income_domain, ['balance:sum'], ['account_id']
        )
        total_income = sum(-line['balance'] for line in income_lines) # Credit is positive

        # 3. Fetch Expenses
        expense_domain = domain + [('account_id.account_type', 'in', ('expense', 'expense_direct_cost', 'expense_depreciation'))]
        expense_lines = self.env['account.move.line'].sudo().read_group(
            expense_domain, ['balance:sum'], ['account_id']
        )
        total_expense = sum(line['balance'] for line in expense_lines)

        net_profit = total_income - total_expense

        # 4. Format Top Expenses for Pie Chart
        expense_breakdown = []
        for line in expense_lines:
            if line['balance'] > 0:
                expense_breakdown.append({
                    'name': line['account_id'][1] if line['account_id'] else 'Unknown',
                    'amount': line['balance']
                })
        # Sort by highest expense and take top 5
        expense_breakdown = sorted(expense_breakdown, key=lambda x: x['amount'], reverse=True)[:5]

        # 5. Monthly Trend for Bar Chart
        trend_data = {}
        all_lines = self.env['account.move.line'].sudo().search(domain + [
            ('account_id.account_type', 'in', ('income', 'income_other', 'expense', 'expense_direct_cost', 'expense_depreciation'))
        ])
        
        for line in all_lines:
            month_str = line.date.strftime('%b %Y') # e.g., 'Jan 2026'
            if month_str not in trend_data:
                trend_data[month_str] = {'income': 0, 'expense': 0}
            
            if line.account_id.account_type in ('income', 'income_other'):
                trend_data[month_str]['income'] += -line.balance
            else:
                trend_data[month_str]['expense'] += line.balance

        # Sort months chronologically
        sorted_months = sorted(trend_data.keys(), key=lambda x: datetime.strptime(x, '%b %Y'))
        
        trend_labels = sorted_months
        trend_income = [trend_data[m]['income'] for m in sorted_months]
        trend_expense = [trend_data[m]['expense'] for m in sorted_months]

        return {
            'total_income': total_income,
            'total_expense': total_expense,
            'net_profit': net_profit,
            'expense_breakdown': expense_breakdown,
            'trend_labels': trend_labels,
            'trend_income': trend_income,
            'trend_expense': trend_expense,
            'date_from': date_from,
            'date_to': date_to,
        }