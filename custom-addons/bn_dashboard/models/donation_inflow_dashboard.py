from odoo import models, fields, api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import calendar

# The amount of an API donation: its local amount, else its amount, as the
# text received (a value that is not a number counts as 0)
_NUMBER = r"'^\s*[-+]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][-+]?[0-9]+)?\s*$'"
API_AMOUNT_SQL = """(CASE
    WHEN COALESCE(total_amount_local, '') <> '' THEN
        CASE WHEN total_amount_local ~ %(n)s THEN total_amount_local::numeric ELSE 0 END
    WHEN COALESCE(total_amount, '') <> '' THEN
        CASE WHEN total_amount ~ %(n)s THEN total_amount::numeric ELSE 0 END
    ELSE 0 END)""".replace('%(n)s', _NUMBER)


class DonationInflowDashboard(models.TransientModel):
    _name = 'donation.inflow.dashboard'
    _description = 'Donation Inflow Dashboard'

    # ------------------------------------------------------------------
    # Segment helpers
    # ------------------------------------------------------------------
    @api.model
    def get_segment_hierarchy(self):
        """Return the analytic-account segment tree (plan name ilike 'Segment')."""
        # the filter lists: names only, read as superuser (a POS / programme
        # manager needs no Accounting rights); the figures keep their own rules
        Account = self.env['account.analytic.account'].sudo()
        seg_l1 = Account.search([('parent_id', '=', False),
                                 ('plan_id.name', 'ilike', 'Segment')])
        seg_l2 = Account.search([('parent_id', 'in', seg_l1.ids)])
        seg_l3 = Account.search([('parent_id', 'in', seg_l2.ids)])
        seg_l4 = Account.search([('parent_id', 'in', seg_l3.ids)])
        return {
            'segments_l1': [{'id': s.id, 'name': s.name} for s in seg_l1],
            'segments_l2': [{'id': s.id, 'name': s.name, 'parent_id': s.parent_id.id} for s in seg_l2],
            'segments_l3': [{'id': s.id, 'name': s.name, 'parent_id': s.parent_id.id} for s in seg_l3],
            'segments_l4': [{'id': s.id, 'name': s.name, 'parent_id': s.parent_id.id} for s in seg_l4],
        }

    def _resolve_segment_account_ids(self, segment_l1, segment_l2, segment_l3, segment_l4, segment_type):
        """Resolve the selected segment level into analytic account IDs (incl. descendants)."""
        seg_id = segment_l4 or segment_l3 or segment_l2 or segment_l1
        if not seg_id and not segment_type:
            return []
        domain = []
        if seg_id:
            domain.append(('id', 'child_of', int(seg_id)))
        if segment_type:
            domain.append(('name', 'ilike', f'%({segment_type})%'))
        return self.env['account.analytic.account'].sudo().search(domain).ids

    def _build_analytic_or_domain(self, model_name, account_ids):
        """
        Build an OR-domain that links a model to the given analytic account IDs.
        Tries, in order:
          1. direct analytic fields on the model itself
          2. via donor_id -> res.partner analytic fields
        Returns [] if no usable link is found (filter silently skipped).
        """
        if not account_ids:
            return []

        model = self.env[model_name]
        or_leaves = []

        # 1) direct analytic fields on the donation model
        if 'analytic_account_id' in model._fields:
            or_leaves.append(('analytic_account_id', 'in', account_ids))
        if 'analytic_account_ids' in model._fields:
            or_leaves.append(('analytic_account_ids', 'in', account_ids))

        # 2) via donor partner
        if 'donor_id' in model._fields:
            donor_field = model._fields['donor_id']
            if donor_field.type == 'many2one' and donor_field.comodel_name == 'res.partner':
                partner = self.env['res.partner']
                donor_ids = set()
                if 'analytic_account_id' in partner._fields:
                    donor_ids.update(
                        partner.search([('analytic_account_id', 'in', account_ids)]).ids
                    )
                if 'analytic_account_ids' in partner._fields:
                    donor_ids.update(
                        partner.search([('analytic_account_ids', 'in', account_ids)]).ids
                    )
                if donor_ids:
                    or_leaves.append(('donor_id', 'in', list(donor_ids)))

        if not or_leaves:
            return []
        if len(or_leaves) == 1:
            return [or_leaves[0]]

        # Combine leaves with left-associative OR
        result = []
        for i in range(len(or_leaves) - 1):
            result.append('|')
            result.append(or_leaves[i])
        result.append(or_leaves[-1])
        return result

    def _append_segment_domains(self, import_domain, api_domain,
                                segment_l1, segment_l2, segment_l3, segment_l4, segment_type):
        """Append the segment filter to both domains, mutating in place."""
        has_filter = bool(segment_l4 or segment_l3 or segment_l2 or segment_l1 or segment_type)
        if not has_filter:
            return
        account_ids = self._resolve_segment_account_ids(
            segment_l1, segment_l2, segment_l3, segment_l4, segment_type
        )
        if not account_ids:
            import_domain.append(('id', '=', 0))
            api_domain.append(('id', '=', 0))
            return
        import_domain.extend(self._build_analytic_or_domain('donation', account_ids))
        api_domain.extend(self._build_analytic_or_domain('api.donation', account_ids))

    # ------------------------------------------------------------------
    # Dashboard data
    # ------------------------------------------------------------------
    @api.model
    def _inflow_sql(self, model, domain):
        """(sub-select of the ids of ``domain``, its params), record rules
        included; None when nothing matches."""
        query = self.env[model]._search(domain)
        if query.is_empty():
            return None
        sub = query.subselect()
        return sub.code, list(sub.params)

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None,
                           segment_l1=None, segment_l2=None, segment_l3=None, segment_l4=None,
                           segment_type=None):
        import_domain = []
        api_domain = []

        if date_from:
            import_domain.append(('date', '>=', date_from))
            api_domain.append(('created_at', '>=', date_from + ' 00:00:00'))
        if date_to:
            import_domain.append(('date', '<=', date_to))
            api_domain.append(('created_at', '<=', date_to + ' 23:59:59'))

        # Segment filter
        self._append_segment_domains(import_domain, api_domain,
                                     segment_l1, segment_l2, segment_l3, segment_l4, segment_type)

        # every figure is computed by PostgreSQL: no donation is loaded in Python
        cr = self.env.cr
        imports, api_donations = self._inflow_sql('donation', import_domain), self._inflow_sql('api.donation', api_domain)
        total_file_amount = total_fee_amount = total_api_amount = 0.0
        file_count = fee_count = api_count = 0
        donor_ids = set()
        if imports:
            cr.execute("SELECT is_fee IS TRUE, COUNT(*), COALESCE(SUM(amount), 0) FROM donation WHERE id IN (%s) GROUP BY 1"
                       % imports[0], imports[1])
            for is_fee, count, amount in cr.fetchall():
                if is_fee:
                    fee_count, total_fee_amount = count, amount
                else:
                    file_count, total_file_amount = count, amount
            cr.execute("SELECT DISTINCT donor_id FROM donation WHERE donor_id IS NOT NULL AND id IN (%s)" % imports[0], imports[1])
            donor_ids.update(r[0] for r in cr.fetchall())
        if api_donations:
            cr.execute("SELECT COUNT(*), COALESCE(SUM(%s), 0) FROM api_donation WHERE id IN (%s)"
                       % (API_AMOUNT_SQL, api_donations[0]), api_donations[1])
            api_count, total_api_amount = cr.fetchone()
            cr.execute("SELECT DISTINCT donor_id FROM api_donation WHERE donor_id IS NOT NULL AND id IN (%s)"
                       % api_donations[0], api_donations[1])
            donor_ids.update(r[0] for r in cr.fetchall())
        total_file_amount, total_fee_amount, total_api_amount = (
            float(total_file_amount), float(total_fee_amount), float(total_api_amount))

        total_amount = total_file_amount + total_fee_amount + total_api_amount
        total_records = file_count + fee_count + api_count
        unique_donors = len(donor_ids)

        # Chart by source
        chart_source = {
            'labels': ['File Donations', 'Fee Collections', 'API Donations'],
            'data': [total_file_amount, total_fee_amount, total_api_amount],
        }

        # Monthly Trend (last 12 months)
        today = datetime.today()
        months = []
        for i in range(11, -1, -1):
            md = today - relativedelta(months=i)
            months.append((md.strftime('%b %Y'), md.strftime('%Y-%m')))
        per_month = {}
        first_day = months[0][1] + '-01'
        if imports:
            # the import date is text (YYYY-MM-DD)
            cr.execute("""SELECT substr(date, 1, 7), SUM(amount) FROM donation
                           WHERE date >= %%s AND id IN (%s) GROUP BY 1""" % imports[0], [first_day] + imports[1])
            for ym, amount in cr.fetchall():
                per_month[ym] = per_month.get(ym, 0.0) + float(amount or 0.0)
        if api_donations:
            cr.execute("""SELECT to_char(created_at, 'YYYY-MM'), SUM(%s) FROM api_donation
                           WHERE created_at >= %%s AND id IN (%s) GROUP BY 1""" % (API_AMOUNT_SQL, api_donations[0]),
                       [first_day] + api_donations[1])
            for ym, amount in cr.fetchall():
                per_month[ym] = per_month.get(ym, 0.0) + float(amount or 0.0)
        chart_monthly = {'labels': [m[0] for m in months], 'data': [per_month.get(m[1], 0.0) for m in months]}

        # Recent combined records: the newest of each source
        recent = []
        Donation = self.env['donation']
        if imports:
            for is_fee, label in ((False, 'File Donation'), (True, 'Fee Collection')):
                records = Donation.search(import_domain + [('is_fee', '=', is_fee)], order='id desc', limit=20)
                for d in records:
                    recent.append({'date': d.date or '', 'name': d.name or '',
                                   'donor': d.donor_id.name or d.name or '',
                                   'type': label, 'amount': d.amount, 'state': d.state})
        if api_donations:
            for d in self.env['api.donation'].search(api_domain, order='created_at desc, id desc', limit=20):
                amt = 0.0
                try:
                    amt = float(d.total_amount_local or d.total_amount or 0.0)
                except ValueError:
                    pass
                recent.append({
                    'date': d.created_at.strftime('%Y-%m-%d') if d.created_at else '',
                    'name': d.dn_number or d.import_id or '',
                    'donor': d.name or d.donor or '',
                    'type': 'API Donation', 'amount': amt, 'state': 'posted',
                })

        recent.sort(key=lambda x: x['date'] or '', reverse=True)
        recent = recent[:20]

        currency = self.env.company.currency_id

        def _fmt(v):
            try:
                val = "{:,.2f}".format(float(v or 0.0))
            except (ValueError, TypeError):
                val = "0.00"
            return ("%s %s" % (val, currency.symbol) if currency.position == 'after'
                    else "%s %s" % (currency.symbol, val))

        return {
            'kpi': {
                'total_amount': _fmt(total_amount),
                'total_records': total_records,
                'unique_donors': unique_donors,
                'file_amount': _fmt(total_file_amount),
                'fee_amount': _fmt(total_fee_amount),
                'api_amount': _fmt(total_api_amount),
            },
            'chart_source': chart_source,
            'chart_monthly': chart_monthly,
            'recent': recent,
        }

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------
    @api.model
    def get_comparison_data(self, mode='month', period1=None, period2=None,
                            segment_l1=None, segment_l2=None, segment_l3=None, segment_l4=None,
                            segment_type=None):
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
            return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')

        p1_start, p1_end = parse_period(period1)
        p2_start, p2_end = parse_period(period2)

        empty = {'p1': {}, 'p2': {}, 'diffs': {}}
        if not p1_start or not p2_start:
            return empty

        def get_stats(start, end):
            d_domain = [('date', '>=', start), ('date', '<=', end)]
            a_domain = [('created_at', '>=', start + ' 00:00:00'),
                        ('created_at', '<=', end + ' 23:59:59')]

            self._append_segment_domains(d_domain, a_domain,
                                         segment_l1, segment_l2, segment_l3, segment_l4, segment_type)

            cr = self.env.cr
            dons, api_dons = self._inflow_sql('donation', d_domain), self._inflow_sql('api.donation', a_domain)
            records, amt, donors = 0, 0.0, set()
            if dons:
                cr.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM donation WHERE id IN (%s)" % dons[0], dons[1])
                count, amount = cr.fetchone()
                records += count
                amt += float(amount)
                cr.execute("SELECT DISTINCT donor_id FROM donation WHERE donor_id IS NOT NULL AND id IN (%s)" % dons[0], dons[1])
                donors.update(r[0] for r in cr.fetchall())
            if api_dons:
                cr.execute("SELECT COUNT(*), COALESCE(SUM(%s), 0) FROM api_donation WHERE id IN (%s)"
                           % (API_AMOUNT_SQL, api_dons[0]), api_dons[1])
                count, amount = cr.fetchone()
                records += count
                amt += float(amount)
                cr.execute("SELECT DISTINCT donor_id FROM api_donation WHERE donor_id IS NOT NULL AND id IN (%s)"
                           % api_dons[0], api_dons[1])
                donors.update(r[0] for r in cr.fetchall())

            return {
                'records': records,
                'amount': amt,
                'donors': len(donors),
            }

        p1 = get_stats(p1_start, p1_end)
        p2 = get_stats(p2_start, p2_end)

        diffs = {}
        for k in p1:
            v1, v2 = p1[k], p2[k]
            d = v2 - v1
            pct = (d / v1 * 100) if v1 > 0 else (100.0 if v2 > 0 else 0.0)
            diffs[k] = {'diff': d, 'pct': pct, 'is_positive': d >= 0}

        return {'p1': p1, 'p2': p2, 'diffs': diffs}