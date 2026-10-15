from odoo import http
from odoo.http import request
from datetime import date, datetime

class TreasuryDashboardController(http.Controller):

    @http.route('/treasury/dashboard/data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_data(self, **kwargs):
        # 1. Calculate Total Cash & Bank Balance (KPI)
        liquidity_accounts = request.env['account.account'].search([('account_type', '=', 'asset_cash')])
        total_cash = sum(liquidity_accounts.mapped('current_balance'))

        # 2. Calculate Total Receivables & Payables (KPI)
        receivables = request.env['account.move.line'].search([
            ('account_id.account_type', '=', 'asset_receivable'),
            ('amount_residual', '>', 0),
            ('parent_state', '=', 'posted')
        ])
        total_receivables = sum(receivables.mapped('amount_residual'))

        payables = request.env['account.move.line'].search([
            ('account_id.account_type', '=', 'liability_payable'),
            ('amount_residual', '>', 0),
            ('parent_state', '=', 'posted')
        ])
        total_payables = sum(payables.mapped('amount_residual'))

        # 3. Customer Invoices Metrics
        today = date.today()
        invoice_domain = [('move_type', '=', 'out_invoice')]
        
        inv_to_validate = request.env['account.move'].search_count(invoice_domain + [('state', '=', 'draft')])
        inv_to_validate_amt = sum(request.env['account.move'].search(invoice_domain + [('state', '=', 'draft')]).mapped('amount_total'))
        
        inv_unpaid = request.env['account.move'].search_count(invoice_domain + [('state', '=', 'posted'), ('payment_state', 'in', ['not_paid', 'partial'])])
        inv_unpaid_amt = sum(request.env['account.move'].search(invoice_domain + [('state', '=', 'posted'), ('payment_state', 'in', ['not_paid', 'partial'])]).mapped('amount_residual'))
        
        inv_late = request.env['account.move'].search_count(invoice_domain + [('state', '=', 'posted'), ('payment_state', 'in', ['not_paid', 'partial']), ('invoice_date_due', '<', today)])
        inv_late_amt = sum(request.env['account.move'].search(invoice_domain + [('state', '=', 'posted'), ('payment_state', 'in', ['not_paid', 'partial']), ('invoice_date_due', '<', today)]).mapped('amount_residual'))

        # 4. Vendor Bills Metrics
        bill_domain = [('move_type', '=', 'in_invoice')]
        
        bill_to_validate = request.env['account.move'].search_count(bill_domain + [('state', '=', 'draft')])
        bill_to_validate_amt = sum(request.env['account.move'].search(bill_domain + [('state', '=', 'draft')]).mapped('amount_total'))
        
        bill_to_pay = request.env['account.move'].search_count(bill_domain + [('state', '=', 'posted'), ('payment_state', 'in', ['not_paid', 'partial'])])
        bill_to_pay_amt = sum(request.env['account.move'].search(bill_domain + [('state', '=', 'posted'), ('payment_state', 'in', ['not_paid', 'partial'])]).mapped('amount_residual'))

        # 5. Bank & Cash Journals Metrics
        journals = request.env['account.journal'].search([('type', 'in', ['bank', 'cash'])])
        journal_data = []
        for journal in journals:
            # Get the journal's current balance from its default account
            balance = sum(journal.default_account_id.mapped('current_balance')) if journal.default_account_id else 0.0
            
            # Count of transactions (Payments/Misc) for this journal in the current month
            start_of_month = today.replace(day=1)
            payments_count = request.env['account.move.line'].search_count([
                ('journal_id', '=', journal.id),
                ('date', '>=', start_of_month),
                ('parent_state', '=', 'posted')
            ])
            
            journal_data.append({
                'id': journal.id,
                'name': journal.name,
                'balance': balance,
                'payments_count': payments_count,
            })

        # 6. Chart Data: Payables vs Receivables grouped by Month (Current Year)
        start_of_year = today.replace(month=1, day=1).strftime('%Y-%m-%d')
        
        receivable_groups = request.env['account.move.line'].read_group(
            [('account_id.account_type', '=', 'asset_receivable'), ('parent_state', '=', 'posted'), ('date', '>=', start_of_year)],
            ['amount_residual:sum'], ['date:month'], lazy=False
        )
        payable_groups = request.env['account.move.line'].read_group(
            [('account_id.account_type', '=', 'liability_payable'), ('parent_state', '=', 'posted'), ('date', '>=', start_of_year)],
            ['amount_residual:sum'], ['date:month'], lazy=False
        )

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
            'invoices': {
                'to_validate': inv_to_validate,
                'to_validate_amt': inv_to_validate_amt,
                'unpaid': inv_unpaid,
                'unpaid_amt': inv_unpaid_amt,
                'late': inv_late,
                'late_amt': inv_late_amt,
            },
            'bills': {
                'to_validate': bill_to_validate,
                'to_validate_amt': bill_to_validate_amt,
                'to_pay': bill_to_pay,
                'to_pay_amt': bill_to_pay_amt,
            },
            'journals': journal_data,
            'chart': {
                'labels': sorted_months,
                'receivables': receivable_data,
                'payables': payable_data,
            }
        }