# -*- coding: utf-8 -*-
from odoo import api, models
from datetime import date
from dateutil.relativedelta import relativedelta
import calendar

class DonationBoxDashboard(models.TransientModel):
    _name = 'donation.box.dashboard'
    _description = 'Donation Box Dashboard'

    @api.model
    def get_location_hierarchy(self):
        provinces = self.env['account.analytic.account'].search([('parent_id', '=', False), ('plan_id.name', '=', 'Location')])
        cities = self.env['account.analytic.account'].search([('parent_id', 'in', provinces.ids)])
        zones = self.env['account.analytic.account'].search([('parent_id', 'in', cities.ids)])
        
        bunches = self.env['key.bunch'].search([])
        schedule_days = self.env['rider.schedule.day'].search([('zone_id', '!=', False), ('key_bunch_id', '!=', False)])
        bunch_zone_map = {sd.key_bunch_id.id: sd.zone_id.id for sd in schedule_days}
        
        bunch_data = [{'id': b.id, 'name': b.name, 'zone_id': bunch_zone_map.get(b.id, False)} for b in bunches]
        
        return {
            'provinces': [{'id': p.id, 'name': p.name} for p in provinces],
            'cities': [{'id': c.id, 'name': c.name, 'province_id': c.parent_id.id} for c in cities],
            'zones': [{'id': z.id, 'name': z.name, 'city_id': z.parent_id.id} for z in zones],
            'bunches': bunch_data,
        }

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None, 
                           province_id=None, city_id=None, zone_id=None, bunch_id=None):
        reg_domain = []
        comp_domain = []
        col_domain = []
        
        base_col_domain = []
        if province_id:
            base_col_domain.append(('donation_box_registration_installation_id.city_id.parent_id', '=', int(province_id)))
        if city_id:
            base_col_domain.append(('donation_box_registration_installation_id.city_id', '=', int(city_id)))
        if zone_id:
            base_col_domain.append(('donation_box_registration_installation_id.zone_id', '=', int(zone_id)))
        if bunch_id:
            base_col_domain.append(('donation_box_registration_installation_id.key_bunch_id', '=', int(bunch_id)))
        
        if date_from:
            reg_domain.append(('installation_date', '>=', date_from))
            comp_domain.append(('date', '>=', date_from))
        if date_to:
            reg_domain.append(('installation_date', '<=', date_to))
            comp_domain.append(('date', '<=', date_to))
            
        reg_domain.extend([d for d in base_col_domain if 'city_id' in d[0] or 'zone_id' in d[0]])
        comp_domain.extend([d for d in base_col_domain if 'city_id' in d[0] or 'zone_id' in d[0]])
            
        col_domain = list(base_col_domain)
        if date_from: col_domain.append(('date', '>=', date_from))
        if date_to: col_domain.append(('date', '<=', date_to))

        Registration = self.env['donation.box.registration.installation']
        Complain = self.env['donation.box.complain.center']
        Collection = self.env['rider.collection']

        draft_boxes = Registration.search_count(reg_domain + [('status', '=', 'draft')])
        available = Registration.search_count(reg_domain + [('status', '=', 'available')])
        installed = Registration.search_count(reg_domain + [('status', '=', 'installed')])
        closed = Registration.search_count(reg_domain + [('status', '=', 'close')])
        
        draft_complaints = Complain.search_count(comp_domain + [('status', '=', 'draft')])
        process_complaints = Complain.search_count(comp_domain + [('status', '=', 'process')])
        resolved_complaints = Complain.search_count(comp_domain + [('status', '=', 'resolved')])

        collections = Collection.search(col_domain)
        total_collection = sum([c.amount for c in collections if c.state in ['donation_submit', 'pending', 'paid']])
        not_collected_count = Collection.search_count(col_domain + [('state', '=', 'donation_not_collected')])
        pending_count = Collection.search_count(col_domain + [('state', '=', 'pending')])
        paid_count = Collection.search_count(col_domain + [('state', '=', 'paid')])

        today = date.today()
        start_3m = (today - relativedelta(months=2)).replace(day=1)
        end_3m = today
        
        start_prev_3m = (start_3m - relativedelta(months=3)).replace(day=1)
        end_prev_3m = start_3m - relativedelta(days=1)

        current_3m_cols = Collection.search(base_col_domain + [
            ('date', '>=', start_3m.strftime('%Y-%m-%d')),
            ('date', '<=', end_3m.strftime('%Y-%m-%d')),
            ('state', 'in', ['donation_submit', 'pending', 'paid'])
        ])
        current_3m_sum = sum(current_3m_cols.mapped('amount'))

        prev_3m_cols = Collection.search(base_col_domain + [
            ('date', '>=', start_prev_3m.strftime('%Y-%m-%d')),
            ('date', '<=', end_prev_3m.strftime('%Y-%m-%d')),
            ('state', 'in', ['donation_submit', 'pending', 'paid'])
        ])
        prev_3m_sum = sum(prev_3m_cols.mapped('amount'))

        diff_pct = 0
        if prev_3m_sum > 0:
            diff_pct = ((current_3m_sum - prev_3m_sum) / prev_3m_sum) * 100
        elif current_3m_sum > 0:
            diff_pct = 100

        today_chart = date.today()
        months = []
        counts = []
        for i in range(5, -1, -1):
            d = today_chart - relativedelta(months=i)
            month_start = d.replace(day=1)
            month_end = d.replace(day=calendar.monthrange(d.year, d.month)[1])
            months.append(d.strftime('%b %Y'))
            count = Registration.search_count(reg_domain + [
                ('installation_date', '>=', month_start.strftime('%Y-%m-%d')),
                ('installation_date', '<=', month_end.strftime('%Y-%m-%d'))
            ])
            counts.append(count)

        installs_by_month = {'labels': months, 'data': counts}

        comp_by_box_status = {}
        comps = Complain.read_group(comp_domain, ['box_status'], ['box_status'])
        for c in comps:
            if c['box_status']:
                comp_by_box_status[c['box_status']] = c['box_status_count']

        recent_complaints = Complain.search_read(comp_domain, ['lot_id', 'shop_name', 'box_status', 'status', 'date'], limit=10, order='id desc')
        recent_registrations = Registration.search_read(reg_domain, ['shop_name', 'lot_id', 'city_id', 'installation_date', 'status'], limit=10, order='id desc')
        recent_collections = Collection.search_read(col_domain, ['date', 'shop_name', 'rider_id', 'lot_id', 'amount', 'state'], limit=10, order='id desc')

        for c in recent_complaints:
            c['lot_name'] = c['lot_id'][1] if c['lot_id'] else '-'
            c['shop_name'] = c['shop_name'] or '-'
        for r in recent_registrations:
            r['lot_name'] = r['lot_id'][1] if r['lot_id'] else '-'
            r['city_name'] = r['city_id'][1] if r['city_id'] else '-'
            r['shop_name'] = r['shop_name'] or '-'
        for col in recent_collections:
            col['rider_name'] = col['rider_id'][1] if col['rider_id'] else '-'
            col['lot_name'] = col['lot_id'][1] if col['lot_id'] else '-'
            col['shop_name'] = col['shop_name'] or '-'

        return {
            'kpi': {
                'draft_boxes': draft_boxes, 'available': available, 'installed': installed, 'closed': closed,
                'draft_complaints': draft_complaints, 'process_complaints': process_complaints, 'resolved_complaints': resolved_complaints,
                'total_collection': "{:,.2f}".format(total_collection),
                'not_collected_count': not_collected_count, 'pending_count': pending_count, 'paid_count': paid_count,
                'collection_3m': "{:,.2f}".format(current_3m_sum),
                'collection_3m_diff': "{:+.1f}%".format(diff_pct),
                'is_positive': diff_pct >= 0,
            },
            'chart_comp_status': {'labels': list(comp_by_box_status.keys()), 'data': list(comp_by_box_status.values())},
            'chart_installs': installs_by_month,
            'recent_complaints': recent_complaints,
            'recent_registrations': recent_registrations,
            'recent_collections': recent_collections,
        }

    @api.model
    def get_comparison_data(self, month_1, month_2, province_id=None, city_id=None, zone_id=None, bunch_id=None):
        # Validate inputs (format YYYY-MM)
        if not month_1 or not month_2:
            return {'m1_sum': 0, 'm2_sum': 0, 'diff': 0, 'pct': 0, 'is_positive': True}

        base_col_domain = []
        if province_id:
            base_col_domain.append(('donation_box_registration_installation_id.city_id.parent_id', '=', int(province_id)))
        if city_id:
            base_col_domain.append(('donation_box_registration_installation_id.city_id', '=', int(city_id)))
        if zone_id:
            base_col_domain.append(('donation_box_registration_installation_id.zone_id', '=', int(zone_id)))
        if bunch_id:
            base_col_domain.append(('donation_box_registration_installation_id.key_bunch_id', '=', int(bunch_id)))

        def get_month_dates(ym_str):
            year, month = map(int, ym_str.split('-'))
            start = date(year, month, 1)
            end = date(year, month, calendar.monthrange(year, month)[1])
            return start, end

        start1, end1 = get_month_dates(month_1)
        start2, end2 = get_month_dates(month_2)

        Collection = self.env['rider.collection']

        # Month 1
        m1_cols = Collection.search(base_col_domain + [
            ('date', '>=', start1.strftime('%Y-%m-%d')),
            ('date', '<=', end1.strftime('%Y-%m-%d')),
            ('state', 'in', ['donation_submit', 'pending', 'paid'])
        ])
        m1_sum = sum(m1_cols.mapped('amount'))

        # Month 2
        m2_cols = Collection.search(base_col_domain + [
            ('date', '>=', start2.strftime('%Y-%m-%d')),
            ('date', '<=', end2.strftime('%Y-%m-%d')),
            ('state', 'in', ['donation_submit', 'pending', 'paid'])
        ])
        m2_sum = sum(m2_cols.mapped('amount'))

        # Diff
        diff = m2_sum - m1_sum
        pct = 0
        if m1_sum > 0:
            pct = (diff / m1_sum) * 100
        elif m2_sum > 0:
            pct = 100

        return {
            'm1_sum': "{:,.2f}".format(m1_sum),
            'm2_sum': "{:,.2f}".format(m2_sum),
            'diff': "{:+,.2f}".format(diff),
            'pct': "{:+.1f}%".format(pct),
            'is_positive': diff >= 0,
        }