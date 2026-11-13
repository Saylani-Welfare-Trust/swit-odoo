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
        # the filter lists: names only, read as superuser (a POS / programme
        # manager needs no Accounting rights); the figures keep their own rules
        seg_l1 = self.env['account.analytic.account'].sudo().search([('parent_id', '=', False), ('plan_id.name', 'ilike', 'Segment')])
        seg_l2 = self.env['account.analytic.account'].sudo().search([('parent_id', 'in', seg_l1.ids)])
        seg_l3 = self.env['account.analytic.account'].sudo().search([('parent_id', 'in', seg_l2.ids)])
        seg_l4 = self.env['account.analytic.account'].sudo().search([('parent_id', 'in', seg_l3.ids)])

        return {
            'segments_l1': [{'id': s.id, 'name': s.name} for s in seg_l1],
            'segments_l2': [{'id': s.id, 'name': s.name, 'parent_id': s.parent_id.id} for s in seg_l2],
            'segments_l3': [{'id': s.id, 'name': s.name, 'parent_id': s.parent_id.id} for s in seg_l3],
            'segments_l4': [{'id': s.id, 'name': s.name, 'parent_id': s.parent_id.id} for s in seg_l4],
        }

    # ------------------------------------------------------------------
    # Domain helper
    # ------------------------------------------------------------------
    @api.model
    def _get_din_domain(self, date_from=None, date_to=None,
                        segment_id=None, segment_type=None, state=None):
        domain = []
        if date_from:
            domain.append(('create_date', '>=', date_from + ' 00:00:00'))
        if date_to:
            domain.append(('create_date', '<=', date_to + ' 23:59:59'))

        # Combine segment hierarchy + segment type filter
        if segment_id and segment_type:
            accounts = self.env['account.analytic.account'].search([
                ('id', 'child_of', int(segment_id)),
                ('name', 'ilike', f'%({segment_type})%'),
            ])
            if accounts:
                domain.append(('analytical_account_id', 'in', accounts.ids))
            else:
                domain.append(('id', '=', 0))
        elif segment_id:
            domain.append(('analytical_account_id', 'child_of', int(segment_id)))
        elif segment_type:
            accounts = self.env['account.analytic.account'].search([
                ('name', 'ilike', f'%({segment_type})%'),
            ])
            if accounts:
                domain.append(('analytical_account_id', 'in', accounts.ids))
            else:
                domain.append(('id', '=', 0))

        if state:
            domain.append(('state', '=', state))
        return domain

    # ------------------------------------------------------------------
    # SQL scope: the donations of the domain (record rules included) with
    # their quantity and value, filtered on the value range. Every figure is
    # computed by PostgreSQL from it: no donation or line is loaded in Python.
    # ------------------------------------------------------------------
    @api.model
    def _din_scope(self, domain, amount_min=None, amount_max=None):
        """(sql, params) of a WITH clause defining ``scope``
        (id, name, donor_id, state, create_date, qty, val), or None when empty."""
        query = self._search(domain)
        if query.is_empty():
            return None
        sub = query.subselect()
        having, params = [], list(sub.params)
        if amount_min is not None:
            having.append('val >= %s')
        if amount_max is not None:
            having.append('val <= %s')
        sql = """
            WITH totals AS (
                SELECT din.id, din.name, din.donor_id, din.state, din.create_date,
                       COALESCE(SUM(l.quantity), 0) AS qty,
                       COALESCE(SUM(l.quantity * l.avg_price), 0) AS val
                  FROM donation_in_kind din
                  LEFT JOIN donation_in_kind_line l ON l.donation_in_kind_id = din.id
                 WHERE din.id IN (%s)
                 GROUP BY din.id
            ), scope AS (SELECT * FROM totals %s)
        """ % (sub.code, ('WHERE ' + ' AND '.join(having)) if having else '')
        if amount_min is not None:
            params.append(float(amount_min))
        if amount_max is not None:
            params.append(float(amount_max))
        return sql, params

    # ------------------------------------------------------------------
    # Main dashboard data
    # ------------------------------------------------------------------
    @api.model
    def get_din_dashboard_data(self, date_from=None, date_to=None,
                               segment_id=None, segment_type=None, state=None,
                               amount_min=None, amount_max=None):
        domain = self._get_din_domain(date_from, date_to, segment_id, segment_type, state)
        scope = self._din_scope(domain, amount_min, amount_max)
        cr = self.env.cr
        state_labels = dict(self._fields['state'].selection)

        total_records = unique_donors = 0
        total_qty = total_value = 0.0
        state_counts, top_donors, top_products, top_categories, recent = {}, [], [], [], []
        today = datetime.today()
        months = []
        for i in range(11, -1, -1):
            md = today - relativedelta(months=i)
            m_start = md.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            months.append((md.strftime('%b %Y'), m_start, (m_start + relativedelta(months=1)) - timedelta(seconds=1)))
        monthly_counts, monthly_values = [0] * 12, [0.0] * 12

        if scope:
            sql, params = scope
            cr.execute(sql + """
                SELECT COUNT(*), COALESCE(SUM(qty), 0), COALESCE(SUM(val), 0), COUNT(DISTINCT donor_id)
                  FROM scope""", params)
            total_records, total_qty, total_value, unique_donors = cr.fetchone()

            cr.execute(sql + "SELECT state, COUNT(*) FROM scope GROUP BY state ORDER BY MAX(id) DESC", params)
            state_counts = dict(cr.fetchall())

            cr.execute(sql + """
                SELECT donor_id, SUM(qty), SUM(val), COUNT(*) FROM scope
                 WHERE donor_id IS NOT NULL GROUP BY donor_id ORDER BY SUM(val) DESC LIMIT 10""", params)
            rows = cr.fetchall()
            names = dict(self.env['res.partner'].browse([r[0] for r in rows]).sudo().mapped(lambda p: (p.id, p.name)))
            top_donors = [{'name': names.get(r[0], ''), 'qty': r[1], 'value': r[2], 'count': r[3]} for r in rows]

            cr.execute(sql + """
                SELECT l.product_id, SUM(l.quantity), SUM(l.quantity * l.avg_price)
                  FROM donation_in_kind_line l JOIN scope s ON s.id = l.donation_in_kind_id
                 WHERE l.product_id IS NOT NULL
                 GROUP BY l.product_id ORDER BY 3 DESC LIMIT 10""", params)
            rows = cr.fetchall()
            names = dict(self.env['product.product'].browse([r[0] for r in rows]).sudo().mapped(lambda p: (p.id, p.name)))
            top_products = [{'name': names.get(r[0], ''), 'qty': r[1], 'value': r[2]} for r in rows]

            cr.execute(sql + """
                SELECT pt.categ_id, SUM(l.quantity), SUM(l.quantity * l.avg_price)
                  FROM donation_in_kind_line l JOIN scope s ON s.id = l.donation_in_kind_id
                  JOIN product_product pp ON pp.id = l.product_id
                  JOIN product_template pt ON pt.id = pp.product_tmpl_id
                 WHERE pt.categ_id IS NOT NULL
                 GROUP BY pt.categ_id ORDER BY 3 DESC LIMIT 10""", params)
            rows = cr.fetchall()
            categories = {c.id: c.complete_name or c.name
                          for c in self.env['product.category'].browse([r[0] for r in rows]).sudo()}
            top_categories = [{'name': categories.get(r[0], ''), 'qty': r[1], 'value': r[2]} for r in rows]

            cr.execute(sql + """
                SELECT date_trunc('month', create_date), COUNT(*), SUM(val) FROM scope
                 WHERE create_date >= %s GROUP BY 1""", params + [months[0][1]])
            per_month = {r[0].strftime('%Y-%m'): (r[1], r[2]) for r in cr.fetchall()}
            for index, (_label, m_start, _m_end) in enumerate(months):
                count, value = per_month.get(m_start.strftime('%Y-%m'), (0, 0.0))
                monthly_counts[index], monthly_values[index] = count, value

            cr.execute(sql + """
                SELECT id, name, donor_id, state, qty, val, create_date FROM scope ORDER BY id DESC LIMIT 20""", params)
            rows = cr.fetchall()
            names = dict(self.env['res.partner'].browse([r[2] for r in rows if r[2]]).sudo().mapped(lambda p: (p.id, p.name)))
            recent = [{
                'id': r[0], 'name': r[1], 'donor': names.get(r[2], '') if r[2] else '',
                'state': r[3], 'state_label': state_labels.get(r[3], r[3]),
                'qty': r[4], 'value': r[5], 'date': r[6].strftime('%Y-%m-%d') if r[6] else '',
            } for r in rows]
        monthly_labels = [m[0] for m in months]

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
                'total_records': total_records,
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
    # Category Group Time Series (display-only)
    # ------------------------------------------------------------------
    @api.model
    def get_din_category_time_series(self, date_from=None, date_to=None,
                                     segment_id=None, segment_type=None, state=None,
                                     amount_min=None, amount_max=None, **kwargs):
        if not date_from and not date_to:
            today = datetime.today()
            date_from = (today - relativedelta(months=11)).replace(day=1).strftime('%Y-%m-%d')
            date_to = today.strftime('%Y-%m-%d')

        domain = self._get_din_domain(date_from, date_to, segment_id, segment_type, state)
        scope = self._din_scope(domain)

        tree = {}
        columns_set = set()
        if scope:
            sql, params = scope
            cr = self.env.cr
            cr.execute(sql + """
                SELECT DISTINCT to_char(create_date, 'YYYY-MM') FROM scope WHERE create_date IS NOT NULL""", params)
            for (ym,) in cr.fetchall():
                columns_set.add((ym, datetime.strptime(ym, '%Y-%m').strftime('%b %y')))
            cr.execute(sql + """
                SELECT pt.categ_id, to_char(s.create_date, 'YYYY-MM'), SUM(l.quantity * l.avg_price)
                  FROM donation_in_kind_line l JOIN scope s ON s.id = l.donation_in_kind_id
                  JOIN product_product pp ON pp.id = l.product_id
                  JOIN product_template pt ON pt.id = pp.product_tmpl_id
                 WHERE pt.categ_id IS NOT NULL AND s.create_date IS NOT NULL
                 GROUP BY 1, 2""", params)
            rows = cr.fetchall()
            categories = {c.id: c.complete_name or c.name
                          for c in self.env['product.category'].browse({r[0] for r in rows}).sudo()}
            for categ_id, ym, value in rows:
                cat_name = categories[categ_id]
                month_label = datetime.strptime(ym, '%Y-%m').strftime('%b %y')
                node = tree.setdefault(cat_name, {'months': {}, 'total': 0.0})
                node['months'][month_label] = node['months'].get(month_label, 0.0) + (value or 0.0)
                node['total'] += value or 0.0

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
                           segment_id=None, segment_type=None, state=None,
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
                segment_id, segment_type, state)
            scope = self._din_scope(domain)
            if not scope:
                return {'records': 0, 'quantity': 0.0, 'value': 0.0, 'donors': 0}
            sql, params = scope
            self.env.cr.execute(sql + """
                SELECT COUNT(*), COALESCE(SUM(qty), 0), COALESCE(SUM(val), 0), COUNT(DISTINCT donor_id)
                  FROM scope""", params)
            records, qty, val, donors = self.env.cr.fetchone()
            return {
                'records': records,
                'quantity': qty,
                'value': val,
                'donors': donors,
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