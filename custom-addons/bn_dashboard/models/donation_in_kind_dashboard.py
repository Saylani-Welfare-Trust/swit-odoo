from odoo import models, fields, api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import calendar


class DonationInKindDashboard(models.Model):
    _inherit = 'donation.in.kind'

    # ------------------------------------------------------------------
    # Filters / hierarchy
    # ------------------------------------------------------------------
    @api.model
    def get_din_hierarchy(self):
        provinces = self.env['account.analytic.account'].search(
            [('parent_id', '=', False), ('plan_id.name', '=', 'Location')])
        cities = self.env['account.analytic.account'].search(
            [('parent_id', 'in', provinces.ids)])
        zones = self.env['account.analytic.account'].search(
            [('parent_id', 'in', cities.ids)])

        branches = self.env['account.analytic.account'].browse(
            list(set(self.search([]).mapped('analytical_account_id').ids)))

        branch_data = []
        for b in branches:
            p = b.parent_id
            zone_id = p.id if p else False
            city_id = p.parent_id.id if p and p.parent_id else False
            province_id = (p.parent_id.parent_id.id
                           if p and p.parent_id and p.parent_id.parent_id else False)
            branch_data.append({
                'id': b.id, 'name': b.name,
                'zone_id': zone_id,
                'city_id': city_id,
                'province_id': province_id,
            })

        return {
            'provinces': [{'id': p.id, 'name': p.name} for p in provinces],
            'cities': [{'id': c.id, 'name': c.name, 'province_id': c.parent_id.id} for c in cities],
            'zones': [{'id': z.id, 'name': z.name, 'city_id': z.parent_id.id} for z in zones],
            'branches': sorted(branch_data, key=lambda x: (x['name'] or '').lower()),
        }

    # ------------------------------------------------------------------
    # Domain helper
    # ------------------------------------------------------------------
    @api.model
    def _get_din_domain(self, date_from=None, date_to=None,
                        province_id=None, city_id=None, zone_id=None,
                        analytic_id=None, state=None):
        domain = []
        if date_from:
            domain.append(('create_date', '>=', date_from + ' 00:00:00'))
        if date_to:
            domain.append(('create_date', '<=', date_to + ' 23:59:59'))
        # --- NEW: Location Restriction ---
        user = self.env.user
        if not user.has_group('base.group_system'):
            allowed_analytic_ids = user.get_allowed_analytic_ids()
            if allowed_analytic_ids:
                domain.append(('analytical_account_id', 'in', allowed_analytic_ids))
            elif user.allowed_location_ids or user.allowed_warehouse_ids:
                domain.append(('id', '=', 0))

        if analytic_id:
            domain.append(('analytical_account_id', '=', int(analytic_id)))
        if province_id:
            domain.append(('analytical_account_id', 'child_of', int(province_id)))
        if city_id:
            domain.append(('analytical_account_id', 'child_of', int(city_id)))
        if zone_id:
            domain.append(('analytical_account_id', 'child_of', int(zone_id)))

        if state:
            domain.append(('state', '=', state))
        return domain

    # ------------------------------------------------------------------
    # Main dashboard data
    # ------------------------------------------------------------------
    @api.model
    def get_din_dashboard_data(self, date_from=None, date_to=None,
                               province_id=None, city_id=None, zone_id=None,
                               analytic_id=None, state=None,
                               amount_min=None, amount_max=None):
        domain = self._get_din_domain(date_from, date_to, province_id, city_id,
                                      zone_id, analytic_id, state)
        donations = self.search(domain, order='id desc')

        # Amount range filter
        if amount_min is not None or amount_max is not None:
            filtered = self.browse()
            amin = float(amount_min) if amount_min is not None else None
            amax = float(amount_max) if amount_max is not None else None
            for d in donations:
                v = sum(l.quantity * l.avg_price for l in d.donation_in_kind_line_ids)
                if amin is not None and v < amin:
                    continue
                if amax is not None and v > amax:
                    continue
                filtered |= d
            donations = filtered

        total_qty = 0.0
        total_value = 0.0
        for d in donations:
            for l in d.donation_in_kind_line_ids:
                total_qty += l.quantity
                total_value += l.quantity * l.avg_price

        unique_donors = len(set(donations.mapped('donor_id').ids))

        state_labels = dict(self._fields['state'].selection)
        state_counts = {}
        for d in donations:
            state_counts[d.state] = state_counts.get(d.state, 0) + 1

        donor_agg = {}
        for d in donations:
            if not d.donor_id:
                continue
            qty = sum(l.quantity for l in d.donation_in_kind_line_ids)
            val = sum(l.quantity * l.avg_price for l in d.donation_in_kind_line_ids)
            did = d.donor_id.id
            if did not in donor_agg:
                donor_agg[did] = {'name': d.donor_id.name, 'qty': 0.0,
                                  'value': 0.0, 'count': 0}
            donor_agg[did]['qty'] += qty
            donor_agg[did]['value'] += val
            donor_agg[did]['count'] += 1
        top_donors = sorted(donor_agg.values(),
                            key=lambda x: x['value'], reverse=True)[:10]

        prod_agg = {}
        for d in donations:
            for l in d.donation_in_kind_line_ids:
                if not l.product_id:
                    continue
                pid = l.product_id.id
                if pid not in prod_agg:
                    prod_agg[pid] = {'name': l.product_id.name, 'qty': 0.0, 'value': 0.0}
                prod_agg[pid]['qty'] += l.quantity
                prod_agg[pid]['value'] += l.quantity * l.avg_price
        top_products = sorted(prod_agg.values(),
                              key=lambda x: x['value'], reverse=True)[:10]

        cat_agg = {}
        for d in donations:
            for l in d.donation_in_kind_line_ids:
                if not l.product_id or not l.product_id.categ_id:
                    continue
                cat_name = l.product_id.categ_id.complete_name or l.product_id.categ_id.name
                if cat_name not in cat_agg:
                    cat_agg[cat_name] = {'name': cat_name, 'qty': 0.0, 'value': 0.0}
                cat_agg[cat_name]['qty'] += l.quantity
                cat_agg[cat_name]['value'] += l.quantity * l.avg_price
        top_categories = sorted(cat_agg.values(),
                                key=lambda x: x['value'], reverse=True)[:10]

        today = datetime.today()
        monthly_labels, monthly_counts, monthly_values = [], [], []
        for i in range(11, -1, -1):
            md = today - relativedelta(months=i)
            m_start = md.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            m_end = (m_start + relativedelta(months=1)) - timedelta(seconds=1)
            monthly_labels.append(md.strftime('%b %Y'))
            m_dons = donations.filtered(lambda d: m_start <= d.create_date <= m_end)
            monthly_counts.append(len(m_dons))
            m_val = sum(sum(l.quantity * l.avg_price
                            for l in d.donation_in_kind_line_ids) for d in m_dons)
            monthly_values.append(m_val)

        recent = []
        for d in donations[:20]:
            qty = sum(l.quantity for l in d.donation_in_kind_line_ids)
            val = sum(l.quantity * l.avg_price for l in d.donation_in_kind_line_ids)
            recent.append({
                'id': d.id,
                'name': d.name,
                'donor': d.donor_id.name if d.donor_id else '',
                'state': d.state,
                'state_label': state_labels.get(d.state, d.state),
                'qty': qty,
                'value': val,
                'date': d.create_date.strftime('%Y-%m-%d') if d.create_date else '',
            })

        currency = self.env.company.currency_id

        def _fmt_money(v):
            try:
                val = "{:,.2f}".format(float(v or 0.0))
            except (TypeError, ValueError):
                val = "0.00"
            return ("%s %s" % (val, currency.symbol) if currency.position == 'after'
                    else "%s %s" % (currency.symbol, val))

        return {
            'kpi': {
                'total_records': len(donations),
                'total_quantity': "{:,.0f}".format(total_qty),
                'total_value': _fmt_money(total_value),
                'unique_donors': unique_donors,
                'state_counts': state_counts,
                'state_labels': state_labels,
                'currency_symbol': currency.symbol,
            },
            'chart_monthly': {
                'labels': monthly_labels,
                'counts': monthly_counts,
                'values': monthly_values,
            },
            'chart_states': {
                'labels': [state_labels.get(k, k) for k in state_counts.keys()],
                'data': list(state_counts.values()),
            },
            'top_donors': top_donors,
            'top_products': top_products,
            'top_categories': top_categories,
            'recent': recent,
        }

    # ------------------------------------------------------------------
    # Category Group Time Series (display-only, not a filter)
    # ------------------------------------------------------------------
    @api.model
    def get_din_category_time_series(self, date_from=None, date_to=None,
                                     province_id=None, city_id=None, zone_id=None,
                                     analytic_id=None, state=None,
                                     amount_min=None, amount_max=None, **kwargs):
        if not date_from and not date_to:
            today = datetime.today()
            date_from = (today - relativedelta(months=11)).replace(day=1).strftime('%Y-%m-%d')
            date_to = today.strftime('%Y-%m-%d')

        domain = self._get_din_domain(date_from, date_to, province_id, city_id,
                                      zone_id, analytic_id, state)
        donations = self.search(domain)

        tree = {}
        columns_set = set()
        for d in donations:
            if not d.create_date:
                continue
            month_label = d.create_date.strftime('%b %y')
            columns_set.add((d.create_date.strftime('%Y-%m'), month_label))
            for l in d.donation_in_kind_line_ids:
                if not l.product_id or not l.product_id.categ_id:
                    continue
                cat_name = l.product_id.categ_id.complete_name or l.product_id.categ_id.name
                if cat_name not in tree:
                    tree[cat_name] = {'months': {}, 'total': 0.0}
                v = l.quantity * l.avg_price
                tree[cat_name]['months'][month_label] = \
                    tree[cat_name]['months'].get(month_label, 0.0) + v
                tree[cat_name]['total'] += v

        sorted_columns = [c[1] for c in sorted(columns_set)]

        def fmt(v):
            try:
                return "{:,.0f}".format(float(v or 0))
            except (TypeError, ValueError):
                return "0"

        rows = []
        col_totals = {c: 0.0 for c in sorted_columns}
        grand_total = 0.0
        for cat_name in sorted(tree.keys(), key=lambda k: tree[k]['total'], reverse=True)[:15]:
            data = tree[cat_name]
            row_months = {}
            for col in sorted_columns:
                val = data['months'].get(col, 0.0)
                row_months[col] = fmt(val)
                col_totals[col] += val
            grand_total += data['total']
            rows.append({
                'name': cat_name,
                'months': row_months,
                'total': fmt(data['total']),
            })

        return {
            'columns': sorted_columns,
            'rows': rows,
            'col_totals': {c: fmt(v) for c, v in col_totals.items()},
            'grand_total': fmt(grand_total),
        }

    # ------------------------------------------------------------------
    # Comparison (Month / Year)
    # ------------------------------------------------------------------
    @api.model
    def get_din_comparison(self, mode='month', period1=None, period2=None,
                           province_id=None, city_id=None, zone_id=None,
                           analytic_id=None, state=None,
                           amount_min=None, amount_max=None, **kwargs):
        def parse_period(p):
            if not p:
                return None, None
            try:
                if mode == 'month':
                    y, m = map(int, str(p).split('-'))
                    start = datetime(y, m, 1)
                    end = datetime(y, m, calendar.monthrange(y, m)[1], 23, 59, 59)
                else:
                    y = int(p)
                    start = datetime(y, 1, 1)
                    end = datetime(y, 12, 31, 23, 59, 59)
            except (ValueError, TypeError):
                return None, None
            return start, end

        s1, e1 = parse_period(period1)
        s2, e2 = parse_period(period2)

        empty = {'p1': {}, 'p2': {}, 'diffs': {},
                 'mode': mode, 'period1': period1, 'period2': period2}
        if not s1 or not s2:
            return empty

        def stats(start, end):
            domain = self._get_din_domain(
                start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'),
                province_id, city_id, zone_id, analytic_id, state)
            dons = self.search(domain)
            qty = sum(sum(l.quantity for l in d.donation_in_kind_line_ids) for d in dons)
            val = sum(sum(l.quantity * l.avg_price
                          for l in d.donation_in_kind_line_ids) for d in dons)
            return {
                'records': len(dons),
                'quantity': qty,
                'value': val,
                'donors': len(set(dons.mapped('donor_id').ids)),
            }

        p1, p2 = stats(s1, e1), stats(s2, e2)

        diffs = {}
        for k in p1:
            v1, v2 = p1[k], p2[k]
            d = v2 - v1
            pct = (d / v1 * 100) if v1 > 0 else (100.0 if v2 > 0 else 0.0)
            diffs[k] = {'diff': d, 'pct': pct, 'is_positive': d >= 0}

        return {'p1': p1, 'p2': p2, 'diffs': diffs,
                'mode': mode, 'period1': period1, 'period2': period2}