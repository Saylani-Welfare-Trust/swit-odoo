from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class TreasuryDashboardController(http.Controller):

    def _get_custom_model_stats(self, model_name, amount_field='amount',
                                state_field='state', date_from=None, date_to=None):
        empty = {
            'count': 0,
            'total_amount': 0.0,
            'states': {},
            'state_amounts': {},
        }

        if model_name not in request.env:
            return empty

        Model = request.env[model_name]

        # Which date field to filter on
        date_field = None
        for possible_field in ['date', 'transfer_date', 'deposit_date', 'create_date']:
            if possible_field in Model._fields:
                date_field = possible_field
                break

        base_domain = []
        if date_field:
            if date_from:
                base_domain.append((date_field, '>=', date_from))
            if date_to:
                base_domain.append((date_field, '<=', date_to))

        has_amount = amount_field in Model._fields

        # ---- 1. Fetch records & total ----
        try:
            records = Model.search(base_domain)
            count = len(records)
            total_amount = sum(records.mapped(amount_field)) if has_amount else 0.0
        except Exception as e:
            _logger.error(f"❌ TREASURY ERROR on {model_name}: {str(e)}")
            return empty

        # ---- 2. Resolve state field ----
        actual_state_field = state_field
        if actual_state_field not in Model._fields:
            if 'status' in Model._fields:
                actual_state_field = 'status'
            elif 'state' in Model._fields:
                actual_state_field = 'state'
            else:
                actual_state_field = None

        # ---- 3. Build states + state_amounts in ONE pass ----
        states = {}
        state_amounts = {}

        if actual_state_field:
            try:
                for rec in records:
                    key = rec[actual_state_field]
                    if not key:
                        continue
                    states[key] = states.get(key, 0) + 1
                    if has_amount:
                        state_amounts[key] = state_amounts.get(key, 0.0) + (rec[amount_field] or 0.0)
            except Exception as e:
                _logger.warning(f"⚠️ TREASURY WARNING (State Badge) on {model_name}: {str(e)}")

        return {
            'count': count,
            'total_amount': total_amount,
            'states': states,
            'state_amounts': state_amounts,   # <-- NEW
        }

    @http.route('/treasury/dashboard/data', type='json', auth='user',
                methods=['POST'], csrf=False)
    def get_dashboard_data(self, date_from=None, date_to=None, **kwargs):
        currency = request.env.company.currency_id

        return {
            'currency': {
                'symbol': currency.symbol,
                'position': currency.position,
            },
            'cheques':   self._get_custom_model_stats('pos.cheque',      'amount', 'state',  date_from, date_to),
            'deposits':  self._get_custom_model_stats('direct.deposit',  'amount', 'state',  date_from, date_to),
            'transfers': self._get_custom_model_stats('journal.transfer','amount', 'status', date_from, date_to),
        }