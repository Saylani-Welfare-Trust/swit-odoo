# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.osv import expression

NEXT_ACTION = {
    'not_received': 'Waiting for slaughter',
    'slaughtered': 'Start Cutting',
    'cutting': 'Create Material Request',
    'material_request': 'End Cutting',
    'done': 'Completed',
}
STATE_COLOR = {
    'not_received': '#6c757d',
    'slaughtered': '#17a2b8',
    'cutting': '#fd7e14',
    'material_request': '#6f42c1',
    'done': '#28a745',
}


class LivestockDashboard(models.TransientModel):
    _name = 'livestock.dashboard'
    _description = 'Livestock Dashboard'

    @api.model
    def get_dashboard_data(self, date_from=False, date_to=False, department=False, province_id=False, city_id=False, zone_id=False, segment_id=False, segment_type=False):
        Slaughter = self.env['livestock.slaugther']

        # ---- domains ----
        date_domain = []
        if date_from:
            date_domain.append(('create_date', '>=', date_from + ' 00:00:00'))
        if date_to:
            date_domain.append(('create_date', '<=', date_to + ' 23:59:59'))

        dept_domain = []
        if department == 'meat':
            dept_domain.append(('is_meat_depart', '=', True))
        elif department == 'goat':
            dept_domain.append(('is_goat_depart', '=', True))
        elif department == 'chicken':
            dept_domain.append(('is_chicken_depart', '=', True))

        # ---- location domain ----
        loc_domain = []
        active_ids = [i for i in (province_id, city_id, zone_id, segment_id) if i]
        if active_ids:
            for a_id in active_ids:
                loc_domain = expression.OR([
                    loc_domain,
                    [
                        '|', '|',
                        ('pos_order_id.config_id.analytic_account_id', 'child_of', a_id),
                        ('pos_order_id.session_id.analytic_account_id', 'child_of', a_id),
                        ('direct_deposit_line_id.direct_deposit_id.analytic_account_id', 'child_of', a_id)
                    ]
                ])

        base = date_domain + dept_domain + loc_domain

        # ---- state counts ----
        states = [k for k, _l in Slaughter._fields['state'].selection]
        state_counts = {k: Slaughter.search_count(base + [('state', '=', k)]) for k in states}
        total = sum(state_counts.values())

        # ---- department split ----
        dept_meat = Slaughter.search_count(base + [('is_meat_depart', '=', True)])
        dept_goat = Slaughter.search_count(base + [('is_goat_depart', '=', True)])
        dept_chicken = Slaughter.search_count(base + [('is_chicken_depart', '=', True)])
        dept_other = max(total - dept_meat - dept_goat - dept_chicken, 0)

        # ---- source split ----
        src_pos = Slaughter.search_count(base + [('pos_order_id', '!=', False)])
        src_dd = Slaughter.search_count(base + [('direct_deposit_line_id', '!=', False)])
        src_api = Slaughter.search_count(base + [('api_donation_item_id', '!=', False)])
        src_donation = Slaughter.search_count(base + [('donation_id', '!=', False)])

        # ---- total value ----
        groups = Slaughter.read_group(base, ['price:sum'], [])
        total_value = (groups[0].get('price') or 0.0) if groups else 0.0

        # ---- monthly trend, last 12 months, honouring the department filter ----
        today = fields.Date.context_today(self)
        first_this_month = today.replace(day=1)
        trend = []
        for i in range(11, -1, -1):
            m_start = first_this_month - relativedelta(months=i)
            m_end = m_start + relativedelta(months=1) - timedelta(days=1)
            m_domain = [
                ('create_date', '>=', str(m_start) + ' 00:00:00'),
                ('create_date', '<=', str(m_end) + ' 23:59:59'),
            ] + dept_domain + loc_domain
            trend.append({
                'label': m_start.strftime('%b %y'),
                'total': Slaughter.search_count(m_domain),
                'done': Slaughter.search_count(m_domain + [('state', '=', 'done')]),
            })

        # ---- recent slaughters ----
        recent = Slaughter.search(base, limit=15, order='create_date desc')
        recent_data = [self._serialize(r) for r in recent]

        # ---- pending actions (slaughtered or material_request) ----
        pending = Slaughter.search(
            base + [('state', 'in', ('slaughtered', 'material_request'))],
            limit=15, order='create_date asc',
        )
        pending_data = [self._serialize(r) for r in pending]

        # ---- top donees ----
        donees = {}
        for r in Slaughter.search(base):
            if not r.donee_id:
                continue
            d = donees.setdefault(r.donee_id.id, {
                'name': r.donee_id.name, 'count': 0, 'value': 0.0,
            })
            d['count'] += 1
            d['value'] += r.price or 0.0
        top_donees = sorted(donees.values(), key=lambda d: d['count'], reverse=True)[:5]

        return {
            'kpis': {
                'total': total,
                'pending': state_counts['not_received'] + state_counts['slaughtered'],
                'in_progress': state_counts['cutting'] + state_counts['material_request'],
                'done': state_counts['done'],
                'total_value': total_value,
            },
            'state_chart': [
                {'key': k, 'label': dict(Slaughter._fields['state'].selection)[k],
                 'count': state_counts[k], 'color': STATE_COLOR[k]}
                for k in states
            ],
            'department_chart': [
                {'label': 'Meat',    'count': dept_meat,    'color': '#dc3545'},
                {'label': 'Goat',    'count': dept_goat,    'color': '#28a745'},
                {'label': 'Chicken', 'count': dept_chicken, 'color': '#ffc107'},
                {'label': 'Other',   'count': dept_other,   'color': '#6c757d'},
            ],
            'source_chart': [
                {'label': 'POS Order',       'count': src_pos,      'color': '#007bff'},
                {'label': 'Direct Deposit',  'count': src_dd,       'color': '#6f42c1'},
                {'label': 'API Donation',    'count': src_api,      'color': '#fd7e14'},
                {'label': 'Import Donation', 'count': src_donation, 'color': '#20c997'},
            ],
            'trend': trend,
            'recent': recent_data,
            'pending_list': pending_data,
            'top_donees': top_donees,
        }

    # ------------------------------------------------------------------
    def _serialize(self, r):
        if r.is_meat_depart:
            dept = 'Meat'
        elif r.is_goat_depart:
            dept = 'Goat'
        elif r.is_chicken_depart:
            dept = 'Chicken'
        else:
            dept = 'Other'
        return {
            'id': r.id,
            'name': r.name or '',
            'product': r.product_id.display_name or '',
            'donee': r.donee_id.name or '',
            'ref': r.ref or '',
            'department': dept,
            'state': dict(r._fields['state'].selection).get(r.state, r.state),
            'state_key': r.state,
            'state_color': STATE_COLOR.get(r.state, '#6c757d'),
            'next_action': NEXT_ACTION.get(r.state, ''),
            'price': r.price or 0.0,
            'date': r.create_date.strftime('%Y-%m-%d') if r.create_date else '',
        }