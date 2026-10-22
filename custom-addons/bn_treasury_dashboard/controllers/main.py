from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class TreasuryDashboardController(http.Controller):

    def _get_custom_model_stats(self, model_name, amount_field='amount',
                                state_field='state', date_from=None, date_to=None,
                                analytic_account_id=None, province_id=None, city=None):
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

        # ---- Branch filter ----
        if analytic_account_id and 'analytic_account_id' in Model._fields:
            try:
                base_domain.append(('analytic_account_id', '=', int(analytic_account_id)))
            except (ValueError, TypeError):
                pass

        # ---- Province filter (Applies only if model has donor_id) ----
        if province_id and 'donor_id' in Model._fields:
            try:
                base_domain.append(('donor_id.state_id', '=', int(province_id)))
            except (ValueError, TypeError):
                pass

        # ---- City filter (Applies only if model has donor_id) ----
        if city and 'donor_id' in Model._fields:
            base_domain.append(('donor_id.city', '=', city))

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
            'state_amounts': state_amounts,
        }

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
        return [
            {'id': a.id, 'name': a.display_name}
            for a in sorted(accounts, key=lambda a: (a.display_name or '').lower())
        ]

    def _get_location_filters(self):
        cr = request.env.cr
        # Get Distinct Provinces from Donors that have Cheques or Deposits
        cr.execute("""
            SELECT DISTINCT state_id FROM res_partner 
            WHERE id IN (
                SELECT donor_id FROM pos_cheque WHERE donor_id IS NOT NULL
                UNION
                SELECT donor_id FROM direct_deposit WHERE donor_id IS NOT NULL
            ) AND state_id IS NOT NULL
        """)
        state_ids = [r[0] for r in cr.fetchall()]
        
        provinces = []
        if state_ids:
            states = request.env['res.country.state'].browse(state_ids)
            provinces = [{'id': s.id, 'name': s.name} for s in states]
            provinces.sort(key=lambda x: x['name'])

        # Get Distinct Cities from Donors
        cr.execute("""
            SELECT DISTINCT city FROM res_partner 
            WHERE id IN (
                SELECT donor_id FROM pos_cheque WHERE donor_id IS NOT NULL
                UNION
                SELECT donor_id FROM direct_deposit WHERE donor_id IS NOT NULL
            ) AND city IS NOT NULL AND city != ''
        """)
        cities = [r[0] for r in cr.fetchall()]
        cities.sort()

        return provinces, cities

    @http.route('/treasury/dashboard/data', type='json', auth='user',
                methods=['POST'], csrf=False)
    def get_dashboard_data(self, date_from=None, date_to=None,
                           analytic_account_id=None, province_id=None, city=None, **kwargs):
        currency = request.env.company.currency_id
        provinces, cities = self._get_location_filters()

        return {
            'currency': {
                'symbol': currency.symbol,
                'position': currency.position,
            },
            'analytic_accounts': self._get_analytic_accounts(),
            'provinces': provinces,
            'cities': cities,
            'cheques':   self._get_custom_model_stats('pos.cheque',      'amount', 'state',  date_from, date_to, analytic_account_id, province_id, city),
            'deposits':  self._get_custom_model_stats('direct.deposit',  'amount', 'state',  date_from, date_to, analytic_account_id, province_id, city),
            'transfers': self._get_custom_model_stats('journal.transfer','amount', 'status', date_from, date_to, analytic_account_id, province_id, city),
        }