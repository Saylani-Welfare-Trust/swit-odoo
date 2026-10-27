from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class TreasuryDashboardController(http.Controller):

    # ------------------------------------------------------------------
    # Helpers for Hierarchy
    # ------------------------------------------------------------------
    def _get_location_hierarchy(self):
        provinces = request.env['account.analytic.account'].search([('parent_id', '=', False), ('plan_id.name', '=', 'Location')])
        cities = request.env['account.analytic.account'].search([('parent_id', 'in', provinces.ids)])
        segments = request.env['account.analytic.account'].search([('plan_id.name', 'ilike', 'Segment')])
        
        return (
            [{'id': p.id, 'name': p.name} for p in provinces],
            [{'id': c.id, 'name': c.name, 'province_id': c.parent_id.id} for c in cities],
            [{'id': s.id, 'name': s.display_name} for s in segments]
        )

    def _get_analytic_accounts(self):
        ids = set()
        for model_name in ['pos.cheque', 'direct.deposit', 'journal.transfer']:
            if model_name in request.env:
                Model = request.env[model_name]
                if 'analytic_account_id' in Model._fields:
                    ids.update(
                        Model.search([('analytic_account_id', '!=', False)])
                        .mapped('analytic_account_id').ids
                    )
        if not ids:
            return []
        
        accounts = request.env['account.analytic.account'].browse(list(ids))
        res = []
        for a in accounts:
            province_id = False
            city_id = False
            parent = a.parent_id
            # Walk up the tree to find the City and Province
            while parent:
                if not parent.parent_id:
                    province_id = parent.id
                elif not parent.parent_id.parent_id:
                    city_id = parent.id
                parent = parent.parent_id
            
            res.append({
                'id': a.id, 
                'name': a.name, 
                'province_id': province_id,
                'city_id': city_id
            })
            
        return sorted(res, key=lambda a: (a['name'] or '').lower())

    # ------------------------------------------------------------------
    # Custom Model Stats
    # ------------------------------------------------------------------
    def _get_custom_model_stats(self, model_name, amount_field='amount',
                                state_field='state', date_from=None, date_to=None,
                                analytic_account_id=None, province_id=None, city_id=None, segment_id=None,
                                amount_min=None, amount_max=None):
        empty = {
            'count': 0,
            'total_amount': 0.0,
            'states': {},
            'state_amounts': {},
        }

        if model_name not in request.env:
            return empty

        Model = request.env[model_name]

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

        if analytic_account_id and 'analytic_account_id' in Model._fields:
            try:
                base_domain.append(('analytic_account_id', '=', int(analytic_account_id)))
            except (ValueError, TypeError):
                pass

        if province_id and 'analytic_account_id' in Model._fields:
            try:
                base_domain.append(('analytic_account_id', 'child_of', int(province_id)))
            except (ValueError, TypeError):
                pass

        if city_id and 'analytic_account_id' in Model._fields:
            try:
                base_domain.append(('analytic_account_id', 'child_of', int(city_id)))
            except (ValueError, TypeError):
                pass
                
        if segment_id and 'analytic_account_id' in Model._fields:
            try:
                base_domain.append(('analytic_account_id', 'child_of', int(segment_id)))
            except (ValueError, TypeError):
                pass

        has_amount = amount_field in Model._fields

        if has_amount:
            if amount_min is not None:
                base_domain.append((amount_field, '>=', float(amount_min)))
            if amount_max is not None:
                base_domain.append((amount_field, '<=', float(amount_max)))

        try:
            records = Model.search(base_domain)
            count = len(records)
            total_amount = sum(records.mapped(amount_field)) if has_amount else 0.0
        except Exception as e:
            _logger.error(f"❌ TREASURY ERROR on {model_name}: {str(e)}")
            return empty

        actual_state_field = state_field
        if actual_state_field not in Model._fields:
            if 'status' in Model._fields:
                actual_state_field = 'status'
            elif 'state' in Model._fields:
                actual_state_field = 'state'
            else:
                actual_state_field = None

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
                _logger.warning(f"⚠️ TREASURY WARNING on {model_name}: {str(e)}")

        return {
            'count': count,
            'total_amount': total_amount,
            'states': states,
            'state_amounts': state_amounts,
        }

    # ------------------------------------------------------------------
    # Main Route
    # ------------------------------------------------------------------
    @http.route('/treasury/dashboard/data', type='json', auth='user',
                methods=['POST'], csrf=False)
    def get_dashboard_data(self, date_from=None, date_to=None,
                           analytic_account_id=None, province_id=None, city_id=None, segment_id=None, 
                           amount_min=None, amount_max=None, **kwargs):
        currency = request.env.company.currency_id
        provinces, cities, segments = self._get_location_hierarchy()

        return {
            'currency': {
                'symbol': currency.symbol,
                'position': currency.position,
            },
            'analytic_accounts': self._get_analytic_accounts(),
            'provinces': provinces,
            'cities': cities,
            'segments': segments,
            'cheques':   self._get_custom_model_stats('pos.cheque',      'amount', 'state',  date_from, date_to, analytic_account_id, province_id, city_id, segment_id, amount_min, amount_max),
            'deposits':  self._get_custom_model_stats('direct.deposit',  'amount', 'state',  date_from, date_to, analytic_account_id, province_id, city_id, segment_id, amount_min, amount_max),
            'transfers': self._get_custom_model_stats('journal.transfer','amount', 'status', date_from, date_to, analytic_account_id, province_id, city_id, segment_id, amount_min, amount_max),
        }