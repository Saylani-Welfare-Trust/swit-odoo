from odoo import http
from odoo.http import request
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class TreasuryDashboardController(http.Controller):

    def _get_custom_model_stats(self, model_name, amount_field='amount', state_field='state', date_from=None, date_to=None):
        if model_name not in request.env:
            return {'count': 0, 'total_amount': 0.0, 'states': {}, 'trend_labels': [], 'trend_data': []}
        
        Model = request.env[model_name]
        
        # Determine which date field to use
        date_field = None
        for possible_field in ['date', 'transfer_date', 'deposit_date', 'create_date']:
            if possible_field in Model._fields:
                date_field = possible_field
                break

        # Build Base Domain for the Cards (Count, Total Amount, Badges)
        base_domain = []
        if date_field:
            if date_from:
                base_domain.append((date_field, '>=', date_from))
            if date_to:
                base_domain.append((date_field, '<=', date_to))

        # 1. Fetch Records & Amount
        try:
            records = Model.search(base_domain)
            count = len(records)
            total_amount = sum(records.mapped(amount_field)) if amount_field in Model._fields else 0.0
        except Exception as e:
            _logger.error(f"❌ TREASURY ERROR on {model_name}: {str(e)}")
            return {'count': 0, 'total_amount': 0.0, 'states': {}, 'trend_labels': [], 'trend_data': []}

        # 2. Fetch Status Badges
        states = {}
        if state_field and state_field in Model._fields:
            try:
                groups = Model.read_group(base_domain, ['id:count'], [state_field], lazy=False)
                for g in groups:
                    state_val = g.get(state_field)
                    if state_val:
                        states[state_val] = g['id_count']
            except Exception as e:
                _logger.warning(f"⚠️ TREASURY WARNING on {model_name}: {str(e)}")

        # 3. Fetch Trend Data
        trend_labels = []
        trend_data = []
        
        # Determine trend period (default to last 6 months if no filter is applied)
        if date_from and date_to:
            start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            end_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            months_diff = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1
            months_diff = min(months_diff, 12) # Cap at 12 months to prevent UI overflow
        else:
            end_date = date.today()
            start_date = end_date.replace(day=1) - relativedelta(months=5)
            months_diff = 6

        try:
            if date_field and amount_field in Model._fields:
                for i in range(months_diff):
                    m = start_date + relativedelta(months=i)
                    trend_labels.append(m.strftime('%b'))

                trend_domain = [(date_field, '>=', start_date.strftime('%Y-%m-%d'))]
                if date_from and date_to:
                     trend_domain.append((date_field, '<=', date_to))

                monthly_groups = Model.read_group(
                    trend_domain,
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
    def get_dashboard_data(self, date_from=None, date_to=None, **kwargs):
        currency = request.env.company.currency_id

        return {
            'currency': {
                'symbol': currency.symbol,
                'position': currency.position,
            },
            'cheques': self._get_custom_model_stats('pos.cheque', 'amount', 'state', date_from, date_to),
            'deposits': self._get_custom_model_stats('direct.deposit', 'amount', 'status', date_from, date_to),
            'transfers': self._get_custom_model_stats('journal.transfer', 'amount', 'status', date_from, date_to),
        }