from odoo import models, fields, api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import calendar

class DonationInflowDashboard(models.TransientModel):
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
            
        imports = self.env['donation'].search(import_domain)
        api_donations = self.env['api.donation'].search(api_domain)
        
        file_donations = imports.filtered(lambda d: not d.is_fee)
        fee_collections = imports.filtered(lambda d: d.is_fee)
        
        total_file_amount = sum(file_donations.mapped('amount'))
        total_fee_amount = sum(fee_collections.mapped('amount'))
        
        total_api_amount = 0.0
        for d in api_donations:
            try:
                amt = float(d.total_amount_local or d.total_amount or 0.0)
                total_api_amount += amt
            except ValueError:
                pass
                
        total_amount = total_file_amount + total_fee_amount + total_api_amount
        total_records = len(file_donations) + len(fee_collections) + len(api_donations)
        
        donor_ids = set()
        donor_ids.update(file_donations.mapped('donor_id').ids)
        donor_ids.update(fee_collections.mapped('donor_id').ids)
        donor_ids.update(api_donations.mapped('donor_id').ids)
        unique_donors = len(donor_ids)
        
        # Chart by source
        chart_source = {
            'labels': ['File Donations', 'Fee Collections', 'API Donations'],
            'data': [total_file_amount, total_fee_amount, total_api_amount]
        }
        
        # Monthly Trend (last 12 months)
        today = datetime.today()
        monthly_labels = []
        monthly_amounts = []
        for i in range(11, -1, -1):
            md = today - relativedelta(months=i)
            m_start = md.replace(day=1, hour=0, minute=0, second=0)
            m_end = (m_start + relativedelta(months=1)) - timedelta(seconds=1)
            monthly_labels.append(md.strftime('%b %Y'))
            
            m_start_str = m_start.strftime('%Y-%m-%d')
            m_end_str = m_end.strftime('%Y-%m-%d')
            
            m_amount = 0.0
            for d in imports:
                if d.date and m_start_str <= d.date <= m_end_str:
                    m_amount += d.amount
            for d in api_donations:
                if d.created_at:
                    d_str = d.created_at.strftime('%Y-%m-%d')
                    if m_start_str <= d_str <= m_end_str:
                        try:
                            m_amount += float(d.total_amount_local or d.total_amount or 0.0)
                        except ValueError:
                            pass
            monthly_amounts.append(m_amount)
            
        chart_monthly = {
            'labels': monthly_labels,
            'data': monthly_amounts
        }
        
        # Recent combined records
        recent = []
        for d in file_donations[:20]:
            recent.append({'date': d.date or '', 'name': d.name or '', 'donor': d.donor_id.name or d.name or '', 'type': 'File Donation', 'amount': d.amount, 'state': d.state})
        for d in fee_collections[:20]:
            recent.append({'date': d.date or '', 'name': d.name or '', 'donor': d.donor_id.name or d.name or '', 'type': 'Fee Collection', 'amount': d.amount, 'state': d.state})
        for d in api_donations[:20]:
            amt = 0.0
            try: amt = float(d.total_amount_local or d.total_amount or 0.0)
            except ValueError: pass
            recent.append({'date': d.created_at.strftime('%Y-%m-%d') if d.created_at else '', 'name': d.dn_number or d.import_id or '', 'donor': d.name or d.donor or '', 'type': 'API Donation', 'amount': amt, 'state': 'posted'})
            
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