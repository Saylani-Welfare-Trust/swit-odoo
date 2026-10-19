from odoo import http
from odoo.http import request
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class TreasuryDashboardController(http.Controller):

    def _get_custom_model_stats(self, model_name, amount_field='amount', state_field='state'):
        """Fetch stats and trend for custom models"""
        # Check if model exists
        if model_name not in request.env:
            _logger.warning(f"Treasury Dashboard: Model '{model_name}' not found in env.")
            return {'count': 0, 'total_amount': 0.0, 'states': {}, 'trend_labels': [], 'trend_data': []}
        
        try:
            Model = request.env[model_name]
            
            # Check if amount_field exists
            if amount_field not in Model._fields:
                _logger.error(f"Treasury Dashboard: Field '{amount_field}' does not exist on model '{model_name}'. Available fields: {list(Model._fields.keys())}")
                return {'count': 0, 'total_amount': 0.0, 'states': {}, 'trend_labels': [], 'trend_data': []}
                
            records = Model.search([])
            total_amount = sum(records.mapped(amount_field))
            
            # 1. Fetch Status Badges
            states = {}
            if state_field and state_field in Model._fields:
                groups = Model.read_group([], ['id:count'], [state_field], lazy=False)
                for g in groups:
                    state_val = g.get(state_field)
                    if state_val:
                        states[state_val] = g['id_count']
            elif state_field:
                _logger.warning(f"Treasury Dashboard: State field '{state_field}' does not exist on model '{model_name}'.")

            # 2. Fetch 6-Month Trend Data
            trend_labels = []
            today = date.today()
            start_date = (today.replace(day=1) - relativedelta(months=5))
            
            # Determine which date field to use
            date_field = 'create_date'
            for possible_field in ['date', 'transfer_date', 'transaction_date', 'deposit_date']:
                if possible_field in Model._fields:
                    date_field = possible_field
                    break

            # Generate the last 6 months labels
            for i in range(6):
                m = start_date + relativedelta(months=i)
                trend_labels.append(m.strftime('%b'))

            # Group by month
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

            return {
                'count': len(records), 
                'total_amount': total_amount, 
                'states': states,
                'trend_labels': trend_labels,
                'trend_data': trend_data
            }
        except Exception as e:
            # THIS WILL NOW PRINT THE EXACT ERROR IN YOUR ODOO LOGS
            _logger.error(f"Treasury Dashboard Error on model {model_name}: {str(e)}")
            return {'count': 0, 'total_amount': 0.0, 'states': {}, 'trend_labels': [], 'trend_data': []}

    @http.route('/treasury/dashboard/data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_data(self, **kwargs):
        currency = request.env.company.currency_id

        return {
            'currency': {
                'symbol': currency.symbol,
                'position': currency.position,
            },
            # If your fields are named differently, change them here:
            'cheques': self._get_custom_model_stats('pos.cheque', amount_field='amount', state_field='state'),
            'deposits': self._get_custom_model_stats('direct.deposit', amount_field='amount', state_field='state'),
            'transfers': self._get_custom_model_stats('journal.transfer', amount_field='amount', state_field='status'),
        }