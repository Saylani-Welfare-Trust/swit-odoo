from odoo import http
from odoo.http import request
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class TreasuryDashboardController(http.Controller):

    def _get_custom_model_stats(self, model_name, amount_field='amount', state_field='state', date_from=None, date_to=None):
        if model_name not in request.env:
            return {'count': 0, 'total_amount': 0.0, 'states': {}}
        
        Model = request.env[model_name]
        
        # Determine which date field to use
        date_field = None
        for possible_field in ['date', 'transfer_date', 'deposit_date', 'create_date']:
            if possible_field in Model._fields:
                date_field = possible_field
                break

        # Build Base Domain for the Cards
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
            return {'count': 0, 'total_amount': 0.0, 'states': {}}

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

        return {
            'count': count, 
            'total_amount': total_amount, 
            'states': states
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