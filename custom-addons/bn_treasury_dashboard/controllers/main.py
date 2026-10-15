from odoo import http
from odoo.http import request
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

class TreasuryDashboardController(http.Controller):

    def _get_custom_model_stats(self, model_name, amount_field='amount', state_field='state'):
        """Helper to safely fetch stats and 6-month trend for custom models"""
        if model_name not in request.env:
            return {'count': 0, 'total_amount': 0.0, 'states': {}, 'trend_labels': [], 'trend_data': []}
        
        try:
            records = request.env[model_name].search([])
            total_amount = sum(records.mapped(amount_field))
            
            # 1. Fetch Status Badges
            states = {}
            if state_field:
                groups = request.env[model_name].read_group([], ['id:count'], [state_field], lazy=False)
                for g in groups:
                    state_val = g.get(state_field)
                    if state_val:
                        states[state_val] = g['id_count']
            
            # 2. Fetch 6-Month Trend Data
            trend_labels = []
            trend_data = [0.0] * 6
            today = date.today()
            start_date = (today.replace(day=1) - relativedelta(months=5))
            
            # Determine which date field to use
            date_field = 'create_date'
            if 'date' in request.env[model_name]._fields:
                date_field = 'date'
            elif 'transfer_date' in request.env[model_name]._fields:
                date_field = 'transfer_date'
            elif 'transaction_date' in request.env[model_name]._fields:
                date_field = 'transaction_date'

            # Generate the last 6 months labels (e.g., ['May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct'])
            for i in range(6):
                m = start_date + relativedelta(months=i)
                trend_labels.append(m.strftime('%b'))

            # Group by month
            monthly_groups = request.env[model_name].read_group(
                [(date_field, '>=', start_date.strftime('%Y-%m-%d'))],
                [amount_field + ':sum'],
                [date_field + ':month'],
                lazy=False
            )
            
            month_map = {}
            for g in monthly_groups:
                month_str = g.get(date_field + ':month')
                if month_str:
                    dt = datetime.strptime(month_str, '%B %Y')
                    month_map[dt.strftime('%b')] = g[amount_field]
            
            trend_data = [month_map.get(m, 0.0) for m in trend_labels]

            return {
                'count': len(records), 
                'total_amount': total_amount, 
                'states': states,
                'trend_labels': trend_labels,
                'trend_data': trend_data
            }
        except Exception as e:
            return {'count': 0, 'total_amount': 0.0, 'states': {}, 'trend_labels': [], 'trend_data': []}

    @http.route('/treasury/dashboard/data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_data(self, **kwargs):
        # Fetch System Currency details
        currency = request.env.company.currency_id

        return {
            'currency': {
                'symbol': currency.symbol,
                'position': currency.position, # 'before' or 'after'
            },
            'cheques': self._get_custom_model_stats('pos.cheque', 'amount', 'state'),
            'deposits': self._get_custom_model_stats('direct.deposit', 'amount', 'state'),
            'transfers': self._get_custom_model_stats('journal.transfer', 'amount', 'status'),
        }