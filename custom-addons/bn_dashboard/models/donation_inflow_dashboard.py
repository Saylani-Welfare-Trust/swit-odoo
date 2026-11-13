from odoo import models, api
from datetime import datetime
from dateutil.relativedelta import relativedelta
import calendar

class DonationInflowDashboard(models.AbstractModel):
    _name = 'donation.inflow.dashboard'
    _description = 'Donation Inflow Dashboard'

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None):
        # Domains
        import_domain = []
        api_domain = []
        
        if date_from:
            import_domain.append(('date', '>=', date_from))
            api_domain.append(('created_at', '>=', date_from + ' 00:00:00'))
        if date_to:
            import_domain.append(('date', '<=', date_to))
            api_domain.append(('created_at', '<=', date_to + ' 23:59:59'))
            
        # Records read through the ORM in batches, then one pass over plain values
        imports = [{'date': d.date, 'name': d.name, 'donor_id': d.donor_id.id, 'amount': d.amount,
                    'state': d.state, 'is_fee': d.is_fee}
                   for d in self.env['donation'].search(import_domain, order='id desc')]
        api_donations = [{'created_at': d.created_at, 'dn_number': d.dn_number, 'import_id': d.import_id,
                          'name': d.name, 'donor': d.donor, 'donor_id': d.donor_id.id,
                          'total_amount_local': d.total_amount_local, 'total_amount': d.total_amount}
                         for d in self.env['api.donation'].search(api_domain, order='id desc')]

        def api_amount(d):
            try:
                return float(d['total_amount_local'] or d['total_amount'] or 0.0)
            except (TypeError, ValueError):
                return 0.0

        file_donations = [d for d in imports if not d['is_fee']]
        fee_collections = [d for d in imports if d['is_fee']]
        total_file_amount = sum(d['amount'] for d in file_donations)
        total_fee_amount = sum(d['amount'] for d in fee_collections)
        total_api_amount = sum(api_amount(d) for d in api_donations)

        total_amount = total_file_amount + total_fee_amount + total_api_amount
        total_records = len(imports) + len(api_donations)
        unique_donors = len({d['donor_id'] for d in imports + api_donations if d['donor_id']})

        # Chart by source
        chart_source = {
            'labels': ['File Donations', 'Fee Collections', 'API Donations'],
            'data': [total_file_amount, total_fee_amount, total_api_amount]
        }

        # Monthly Trend (last 12 months): each record added to its month
        today = datetime.today()
        month_keys = [(today - relativedelta(months=i)).strftime('%Y-%m') for i in range(11, -1, -1)]
        by_month = dict.fromkeys(month_keys, 0.0)
        for d in imports:
            key = (d['date'] or '')[:7]
            if key in by_month:
                by_month[key] += d['amount']
        for d in api_donations:
            key = d['created_at'].strftime('%Y-%m') if d['created_at'] else ''
            if key in by_month:
                by_month[key] += api_amount(d)
        chart_monthly = {
            'labels': [datetime.strptime(k, '%Y-%m').strftime('%b %Y') for k in month_keys],
            'data': [by_month[k] for k in month_keys],
        }

        # Recent combined records (names looked up for these only)
        shown = {d['donor_id'] for d in file_donations[:20] + fee_collections[:20] if d['donor_id']}
        donor_names = {p.id: p.name for p in self.env['res.partner'].browse(list(shown))}
        recent = []
        for d in file_donations[:20]:
            recent.append({'date': d['date'] or '', 'name': d['name'] or '', 'donor': donor_names.get(d['donor_id']) or d['name'] or '', 'type': 'File Donation', 'amount': d['amount'], 'state': d['state']})
        for d in fee_collections[:20]:
            recent.append({'date': d['date'] or '', 'name': d['name'] or '', 'donor': donor_names.get(d['donor_id']) or d['name'] or '', 'type': 'Fee Collection', 'amount': d['amount'], 'state': d['state']})
        for d in api_donations[:20]:
            recent.append({'date': d['created_at'].strftime('%Y-%m-%d') if d['created_at'] else '', 'name': d['dn_number'] or d['import_id'] or '', 'donor': d['name'] or d['donor'] or '', 'type': 'API Donation', 'amount': api_amount(d), 'state': 'posted'})

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

    @api.model
    def get_comparison_data(self, mode='month', period1=None, period2=None):
        def parse_period(p):
            if not p: return None, None
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
            a_domain = [('created_at', '>=', start + ' 00:00:00'), ('created_at', '<=', end + ' 23:59:59')]
            
            dons = self.env['donation'].search(d_domain)
            api_dons = self.env['api.donation'].search(a_domain)
            
            amt = sum(dons.mapped('amount'))
            for d in api_dons:
                try: amt += float(d.total_amount_local or d.total_amount or 0.0)
                except ValueError: pass
                
            return {
                'records': len(dons) + len(api_dons),
                'amount': amt,
                'donors': len(set(dons.mapped('donor_id').ids + api_dons.mapped('donor_id').ids))
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