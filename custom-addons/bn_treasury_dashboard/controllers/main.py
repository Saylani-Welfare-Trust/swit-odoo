from odoo import http
from odoo.http import request
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class TreasuryDashboardController(http.Controller):

    def _get_custom_model_stats(self, model_name, amount_field='amount', state_field='state'):
        if model_name not in request.env:
            return {'count': 0, 'total_amount': 0.0, 'states': {}, 'trend_labels': [], 'trend_data': []}
        
        Model = request.env[model_name]
        
        # 1. Fetch Records (This will fail if Access Rights are missing)
        try:
            records = Model.search([])
            count = len(records)
            total_amount = sum(records.mapped(amount_field)) if amount_field in Model._fields else 0.0
        except Exception as e:
            _logger.error(f"❌ TREASURY ERROR (Access/Fields) on {model_name}: {str(e)}")
            return {'count': 0, 'total_amount': 0.0, 'states': {}, 'trend_labels': [], 'trend_data': []}

        # 2. Fetch Status Badges
        states = {}
        if state_field and state_field in Model._fields:
            try:
                groups = Model.read_group([], ['id:count'], [state_field], lazy=False)
                for g in groups:
                    state_val = g.get(state_field)
                    if state_val:
                        states[state_val] = g['id_count']
            except Exception as e:
                _logger.warning(f"⚠️ TREASURY WARNING (State Badge) on {model_name}: {str(e)}")

        # 3. Fetch 6-Month Trend Data (Wrapped safely)
        trend_labels = []
        trend_data = [0.0] * 6
        today = date.today()
        start_date = (today.replace(day=1) - relativedelta(months=5))
        
        # Determine which date field to use based on your screenshots
        date_field = None
        for possible_field in ['date', 'transfer_date', 'deposit_date', 'create_date']:
            if possible_field in Model._fields:
                date_field = possible_field
                break

        try:
            if date_field and amount_field in Model._fields:
                for i in range(6):
                    m = start_date + relativedelta(months=i)
                    trend_labels.append(m.strftime('%b'))

                monthly_groups = Model.read_group(
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
        except Exception as e:
            _logger.error(f"❌ TREASURY ERROR (Trend Chart) on {model_name}: {str(e)}")

        return {
            'count': count, 
            'total_amount': total_amount, 
            'states': states,
            'trend_labels': trend_labels,
            'trend_data': trend_data
        }

    @http.route('/treasury/dashboard/data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_data(self, **kwargs):
        currency = request.env.company.currency_id

        return {
            'currency': {
                'symbol': currency.symbol,
                'position': currency.position,
            },
            # Based on your screenshots: 
            # Cheques has 'amount' and 'state'
            'cheques': self._get_custom_model_stats('pos.cheque', amount_field='amount', state_field='state'),
            # Deposits has 'amount' and 'status' (or state)
            'deposits': self._get_custom_model_stats('direct.deposit', amount_field='amount', state_field='status'),
            # Transfers is working
            'transfers': self._get_custom_model_stats('journal.transfer', amount_field='amount', state_field='status'),
        }