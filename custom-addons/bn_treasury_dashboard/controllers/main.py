from odoo import http
from odoo.http import request
from datetime import datetime, date
import logging

_logger = logging.getLogger(__name__)

class TreasuryDashboardController(http.Controller):

    def _get_custom_model_stats(self, model_name, amount_field='amount', state_field='state', date_from=None, date_to=None):
        if model_name not in request.env:
            return {'count': 0, 'total_amount': 0.0, 'states': {}, 'trend': {'labels': [], 'data': []}}
        
        Model = request.env[model_name]
        
        # Determine date field
        date_field = None
        for possible_field in ['date', 'transfer_date', 'deposit_date', 'create_date']:
            if possible_field in Model._fields:
                date_field = possible_field
                break

        # Base domain for cards
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
            return {'count': 0, 'total_amount': 0.0, 'states': {}, 'trend': {'labels': [], 'data': []}}

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

        # 3. Fetch Graph Data (Dynamic Grouping)
        trend_labels, trend_data = [], []
        if date_field and amount_field in Model._fields:
            try:
                # Determine grouping based on date difference
                group_by = 'month' # Default
                if date_from and date_to:
                    d1 = datetime.strptime(date_from, '%Y-%m-%d').date()
                    d2 = datetime.strptime(date_to, '%Y-%m-%d').date()
                    diff_days = (d2 - d1).days
                    
                    if diff_days <= 31:
                        group_by = 'day'
                    elif diff_days <= 365:
                        group_by = 'month'
                    else:
                        group_by = 'year'
                else:
                    # Default to current year months if no filter
                    date_from = date.today().replace(month=1, day=1).strftime('%Y-%m-%d')
                    date_to = date.today().strftime('%Y-%m-%d')
                    base_domain = [(date_field, '>=', date_from), (date_field, '<=', date_to)]

                graph_groups = Model.read_group(
                    base_domain, [amount_field + ':sum'], [date_field + ':' + group_by], lazy=False
                )
                
                for g in graph_groups:
                    raw_label = g.get(date_field + ':' + group_by)
                    val = g.get(amount_field, 0.0)
                    if raw_label:
                        # Format labels to be readable
                        if group_by == 'month':
                            dt = datetime.strptime(raw_label, '%B %Y')
                            trend_labels.append(dt.strftime('%b %Y'))
                        elif group_by == 'day':
                            dt = datetime.strptime(raw_label, '%Y-%m-%d')
                            trend_labels.append(dt.strftime('%d %b'))
                        else:
                            trend_labels.append(str(raw_label))
                        trend_data.append(val)
            except Exception as e:
                _logger.error(f"❌ TREASURY ERROR (Graph) on {model_name}: {str(e)}")

        return {
            'count': count, 
            'total_amount': total_amount, 
            'states': states,
            'trend': {'labels': trend_labels, 'data': trend_data}
        }

    @http.route('/treasury/dashboard/data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_data(self, date_from=None, date_to=None, **kwargs):
        currency = request.env.company.currency_id

        return {
            'currency': {'symbol': currency.symbol, 'position': currency.position},
            'cheques': self._get_custom_model_stats('pos.cheque', 'amount', 'state', date_from, date_to),
            'deposits': self._get_custom_model_stats('direct.deposit', 'amount', 'status', date_from, date_to),
            'transfers': self._get_custom_model_stats('journal.transfer', 'amount', 'status', date_from, date_to),
        }