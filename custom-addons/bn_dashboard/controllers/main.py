from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class TreasuryDashboardController(http.Controller):

    def _get_location_hierarchy(self):
        restriction = request.env['dashboard.configurator'].get_user_restrictions('treasury')
        
        # 1. Provinces (Filtered)
        province_domain = [('parent_id', '=', False), ('plan_id.name', '=', 'Location')]
        if restriction and restriction['provinces']:
            province_domain.append(('id', 'in', restriction['provinces']))
        provinces = request.env['account.analytic.account'].search(province_domain)

        # 2. Cities (Filtered)
        city_domain = [('parent_id', 'in', provinces.ids)]
        if restriction and restriction['analytic_ids']:
            city_domain.append('|')
            city_domain.append(('id', 'in', restriction['analytic_ids']))
            city_domain.append(('parent_id', 'in', restriction['provinces']))
        cities = request.env['account.analytic.account'].search(city_domain)

        # 3. Zones (Filtered)
        zone_domain = [('parent_id', 'in', cities.ids)]
        if restriction and restriction['analytic_ids']:
            zone_domain.append('|')
            zone_domain.append(('id', 'in', restriction['analytic_ids']))
            zone_domain.append(('parent_id', 'in', restriction['analytic_ids']))
        zones = request.env['account.analytic.account'].search(zone_domain)

        # 4. Segments (Unrestricted for Treasury)
        seg_l1 = request.env['account.analytic.account'].search([('parent_id', '=', False), ('plan_id.name', 'ilike', 'Segment')])
        seg_l2 = request.env['account.analytic.account'].search([('parent_id', 'in', seg_l1.ids)])
        seg_l3 = request.env['account.analytic.account'].search([('parent_id', 'in', seg_l2.ids)])
        seg_l4 = request.env['account.analytic.account'].search([('parent_id', 'in', seg_l3.ids)])
        
        return (
            [{'id': p.id, 'name': p.name} for p in provinces],
            [{'id': c.id, 'name': c.name, 'province_id': c.parent_id.id} for c in cities],
            [{'id': z.id, 'name': z.name, 'city_id': z.parent_id.id} for z in zones],
            [{'id': s.id, 'name': s.name} for s in seg_l1],
            [{'id': s.id, 'name': s.name, 'parent_id': s.parent_id.id} for s in seg_l2],
            [{'id': s.id, 'name': s.name, 'parent_id': s.parent_id.id} for s in seg_l3],
            [{'id': s.id, 'name': s.name, 'parent_id': s.parent_id.id} for s in seg_l4]
        )

    def _get_analytic_accounts(self):
        restriction = request.env['dashboard.configurator'].get_user_restrictions('treasury')
        ids = set()
        
        for model_name in ['pos.cheque', 'direct.deposit', 'journal.transfer']:
            if model_name in request.env:
                Model = request.env[model_name]
                if 'analytic_account_id' in Model._fields:
                    domain = [('analytic_account_id', '!=', False)]
                    if restriction and restriction['analytic_ids']:
                        domain.append(('analytic_account_id', 'child_of', restriction['analytic_ids']))
                    ids.update(Model.search(domain).mapped('analytic_account_id').ids)
        
        if not ids: return []
        
        accounts = request.env['account.analytic.account'].browse(list(ids))
        res = []
        for a in accounts:
            zone_id, city_id, province_id = False, False, False
            parent = a.parent_id
            if parent:
                zone_id = parent.id
                city_parent = parent.parent_id
                if city_parent:
                    city_id = city_parent.id
                    prov_parent = city_parent.parent_id
                    if prov_parent:
                        province_id = prov_parent.id
            
            res.append({
                'id': a.id, 'name': a.name, 
                'zone_id': zone_id, 'city_id': city_id, 'province_id': province_id
            })
        return sorted(res, key=lambda a: (a['name'] or '').lower())

    def _get_custom_model_stats(self, model_name, amount_field='amount', state_field='state', date_from=None, date_to=None,
                                analytic_account_id=None, province_id=None, city_id=None, zone_id=None, segment_id=None,
                                amount_min=None, amount_max=None):
        empty = {'count': 0, 'total_amount': 0.0, 'states': {}, 'state_amounts': {}}
        if model_name not in request.env: return empty

        Model = request.env[model_name]
        date_field = next((f for f in ['date', 'transfer_date', 'deposit_date', 'create_date'] if f in Model._fields), None)

        base_domain = []
        if date_field:
            if date_from: base_domain.append((date_field, '>=', date_from))
            if date_to: base_domain.append((date_field, '<=', date_to))

        # === APPLY RESTRICTION ===
        restriction = request.env['dashboard.configurator'].get_user_restrictions('treasury')
        if restriction and restriction['analytic_ids'] and 'analytic_account_id' in Model._fields:
            base_domain.append(('analytic_account_id', 'child_of', restriction['analytic_ids']))

        # Apply UI dropdown filters
        if analytic_account_id and 'analytic_account_id' in Model._fields:
            try: base_domain.append(('analytic_account_id', '=', int(analytic_account_id)))
            except: pass
        if province_id and 'analytic_account_id' in Model._fields:
            try: base_domain.append(('analytic_account_id', 'child_of', int(province_id)))
            except: pass
        if city_id and 'analytic_account_id' in Model._fields:
            try: base_domain.append(('analytic_account_id', 'child_of', int(city_id)))
            except: pass
        if zone_id and 'analytic_account_id' in Model._fields:
            try: base_domain.append(('analytic_account_id', 'child_of', int(zone_id)))
            except: pass

        has_amount = amount_field in Model._fields
        if has_amount:
            if amount_min is not None: base_domain.append((amount_field, '>=', float(amount_min)))
            if amount_max is not None: base_domain.append((amount_field, '<=', float(amount_max)))

        try:
            records = Model.search(base_domain)
            count = len(records)
            total_amount = sum(records.mapped(amount_field)) if has_amount else 0.0
        except Exception as e:
            _logger.error(f"❌ TREASURY ERROR on {model_name}: {str(e)}")
            return empty

        actual_state_field = state_field if state_field in Model._fields else ('status' if 'status' in Model._fields else ('state' if 'state' in Model._fields else None))
        states, state_amounts = {}, {}

        if actual_state_field:
            for rec in records:
                key = rec[actual_state_field]
                if not key: continue
                states[key] = states.get(key, 0) + 1
                if has_amount: state_amounts[key] = state_amounts.get(key, 0.0) + (rec[amount_field] or 0.0)

        return {'count': count, 'total_amount': total_amount, 'states': states, 'state_amounts': state_amounts}

    @http.route('/treasury/dashboard/data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_data(self, **kwargs):
        currency = request.env.company.currency_id
        p, c, z, s1, s2, s3, s4 = self._get_location_hierarchy()
        
        # Send restriction to frontend so dropdowns can hide/auto-select
        restriction = request.env['dashboard.configurator'].get_user_restrictions('treasury')

        return {
            'currency': {'symbol': currency.symbol, 'position': currency.position},
            'analytic_accounts': self._get_analytic_accounts(),
            'provinces': p, 'cities': c, 'zones': z,
            'segments_l1': s1, 'segments_l2': s2, 'segments_l3': s3, 'segments_l4': s4,
            'restriction': restriction,
            'cheques':   self._get_custom_model_stats('pos.cheque', 'amount', 'state', **kwargs),
            'deposits':  self._get_custom_model_stats('direct.deposit', 'amount', 'state', **kwargs),
            'transfers': self._get_custom_model_stats('journal.transfer', 'amount', 'status', **kwargs),
        }