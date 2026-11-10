from odoo import models, api
from datetime import datetime
from dateutil.relativedelta import relativedelta
import calendar


class DonationInKindDashboard(models.Model):
    _inherit = 'donation.in.kind'

    # ------------------------------------------------------------------
    # Filters / hierarchy
    # ------------------------------------------------------------------
    @api.model
    def get_din_hierarchy(self):
        seg_l1 = self.env['account.analytic.account'].search([('parent_id', '=', False), ('plan_id.name', 'ilike', 'Segment')])
        seg_l2 = self.env['account.analytic.account'].search([('parent_id', 'in', seg_l1.ids)])
        seg_l3 = self.env['account.analytic.account'].search([('parent_id', 'in', seg_l2.ids)])
        seg_l4 = self.env['account.analytic.account'].search([('parent_id', 'in', seg_l3.ids)])

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
    # Main dashboard data
    # ------------------------------------------------------------------
    @api.model
    def get_din_dashboard_data(self, date_from=None, date_to=None,
                               segment_id=None, segment_type=None, state=None,
                               amount_min=None, amount_max=None):
        domain = self._get_din_domain(date_from, date_to, segment_id, segment_type, state)
        # Read once, as plain data (two queries), then aggregate in one pass.
        # Records read through the ORM in batches (no per-record queries), then
        # everything aggregated in one pass.
        records = self.search(domain, order='id desc')
        donations = [{'id': d.id, 'name': d.name, 'donor_id': d.donor_id.id, 'state': d.state,
                      'create_date': d.create_date} for d in records]
        per_donation, products, categories = {}, {}, {}
        for l in records.donation_in_kind_line_ids:
            entry = per_donation.setdefault(l.donation_in_kind_id.id, {'qty': 0.0, 'value': 0.0, 'lines': []})
            row = {'product_id': l.product_id.id, 'quantity': l.quantity, 'avg_price': l.avg_price}
            entry['qty'] += l.quantity
            entry['value'] += l.quantity * l.avg_price
            entry['lines'].append(row)
            if l.product_id and l.product_id.id not in products:
                categ = l.product_id.categ_id
                products[l.product_id.id] = {'name': l.product_id.name, 'categ_id': categ.id}
                if categ:
                    categories[categ.id] = categ.complete_name or categ.name
        empty = {'qty': 0.0, 'value': 0.0, 'lines': []}

        # Amount range filter
        if amount_min is not None or amount_max is not None:
            amin = float(amount_min) if amount_min is not None else None
            amax = float(amount_max) if amount_max is not None else None
            donations = [d for d in donations
                         if (amin is None or per_donation.get(d['id'], empty)['value'] >= amin)
                         and (amax is None or per_donation.get(d['id'], empty)['value'] <= amax)]

        state_labels = dict(self._fields['state'].selection)
        total_qty = total_value = 0.0
        state_counts, donor_agg, prod_agg, cat_agg = {}, {}, {}, {}
        today = datetime.today()
        months = []
        for i in range(11, -1, -1):
            m_start = (today - relativedelta(months=i)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            months.append([m_start, m_start + relativedelta(months=1), 0, 0.0])
        for d in donations:
            agg = per_donation.get(d['id'], empty)
            total_qty += agg['qty']
            total_value += agg['value']
            state_counts[d['state']] = state_counts.get(d['state'], 0) + 1
            if d['donor_id']:
                donor = donor_agg.setdefault(d['donor_id'], {'id': d['donor_id'], 'qty': 0.0, 'value': 0.0, 'count': 0})
                donor['qty'] += agg['qty']
                donor['value'] += agg['value']
                donor['count'] += 1
            for l in agg['lines']:
                if not l['product_id']:
                    continue
                product = products.get(l['product_id'], {})
                value = l['quantity'] * l['avg_price']
                prod = prod_agg.setdefault(l['product_id'], {'name': product.get('name') or '', 'qty': 0.0, 'value': 0.0})
                prod['qty'] += l['quantity']
                prod['value'] += value
                if product.get('categ_id'):
                    cat_name = categories.get(product['categ_id'], '')
                    cat = cat_agg.setdefault(cat_name, {'name': cat_name, 'qty': 0.0, 'value': 0.0})
                    cat['qty'] += l['quantity']
                    cat['value'] += value
            created = d['create_date']
            for month in months:
                if created and month[0] <= created < month[1]:
                    month[2] += 1
                    month[3] += agg['value']
                    break
        unique_donors = len(donor_agg)
        top_donors = sorted(donor_agg.values(), key=lambda x: x['value'], reverse=True)[:10]
        shown = {d['donor_id'] for d in donations[:20] if d['donor_id']} | {d['id'] for d in top_donors}
        donor_names = {p.id: p.name for p in self.env['res.partner'].browse(list(shown))}
        for d in top_donors:
            d['name'] = donor_names.get(d.pop('id'), '')
        top_products = sorted(prod_agg.values(), key=lambda x: x['value'], reverse=True)[:10]
        top_categories = sorted(cat_agg.values(), key=lambda x: x['value'], reverse=True)[:10]
        monthly_labels = [m[0].strftime('%b %Y') for m in months]
        monthly_counts = [m[2] for m in months]
        monthly_values = [m[3] for m in months]

        recent = []
        for d in donations[:20]:
            agg = per_donation.get(d['id'], empty)
            recent.append({
                'id': d['id'],
                'name': d['name'],
                'donor': donor_names.get(d['donor_id'], '') if d['donor_id'] else '',
                'state': d['state'],
                'state_label': state_labels.get(d['state'], d['state']),
                'qty': agg['qty'],
                'value': agg['value'],
                'date': d['create_date'].strftime('%Y-%m-%d') if d['create_date'] else '',
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