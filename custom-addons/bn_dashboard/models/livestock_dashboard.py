# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.osv import expression

NEXT_ACTION = {
    'not_received': 'Waiting for slaughter',
    'slaughtered': 'Start Cutting',
    'cutting': 'Create Split',
    'material_request': 'Send to Goat & Meat',
    'done': 'Completed',
}
STATE_COLOR = {
    'not_received': '#6c757d',
    'slaughtered': '#17a2b8',
    'cutting': '#fd7e14',
    'material_request': '#6f42c1',
    'done': '#28a745',
}


class LivestockDashboard(models.AbstractModel):
    """Figures of the Livestock Dashboard: no records of its own, read with the
    user's rights (record rules of the slaughters apply)."""
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

        # ---- location domain: the most precise level chosen (zone > city > province),
        # matched on the branch of the POS / direct deposit the animal came from ----
        loc_domain = []
        location_id = zone_id or city_id or province_id
        if location_id:
            location_id = int(location_id)
            loc_domain = [
                '|', '|',
                ('pos_order_id.config_id.analytic_account_id', 'child_of', location_id),
                ('pos_order_id.session_id.analytic_account_id', 'child_of', location_id),
                ('direct_deposit_line_id.direct_deposit_id.analytic_account_id', 'child_of', location_id),
            ]
        # ---- segment: carried by the product (as on the POS dashboard) ----
        if segment_id or segment_type:
            segment_domain = []
            if segment_id:
                segment_domain.append(('id', 'child_of', int(segment_id)))
            if segment_type:
                segment_domain.append(('name', 'ilike', '(%s)' % segment_type))
            segments = self.env['account.analytic.account'].sudo().search(segment_domain)
            loc_domain = expression.AND([
                loc_domain, [('product_id.product_tmpl_id.analytic_account_id', 'in', segments.ids)]])

        base = date_domain + dept_domain + loc_domain

        # ---- state counts ----
        states = [k for k, _l in Slaughter._fields['state'].selection]
        counts = dict(Slaughter._read_group(base, ['state'], ['__count']))
        state_counts = {k: counts.get(k, 0) for k in states}
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
        total_value = Slaughter._read_group(base, [], ['price:sum'])[0][0] or 0.0

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
        # grouped in the database: no need to load every slaughter
        top_donees = [
            {'name': donee.name, 'count': count, 'value': value or 0.0}
            for donee, count, value in Slaughter._read_group(
                base + [('donee_id', '!=', False)], ['donee_id'], ['__count', 'price:sum'],
                order='__count desc', limit=5)
        ]

        return {
            'kpis': {
                'total': total,
                'pending': state_counts.get('not_received', 0) + state_counts.get('slaughtered', 0),
                'in_progress': state_counts.get('cutting', 0) + state_counts.get('material_request', 0),
                'done': state_counts.get('done', 0),
                'total_value': total_value,
            },
            'state_chart': [
                {'key': k, 'label': dict(Slaughter._fields['state'].selection)[k],
                 'count': state_counts[k], 'color': STATE_COLOR.get(k, '#6c757d')}
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