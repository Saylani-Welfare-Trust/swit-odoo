from odoo import api, models
from datetime import date
from dateutil.relativedelta import relativedelta
import calendar

class DonationBoxDashboard(models.TransientModel):
    _name = 'donation.box.dashboard'
    _description = 'Donation Box Dashboard'

    @api.model
    def get_location_hierarchy(self):
        restriction = self.env['dashboard.configurator'].get_user_restrictions('donation_box')

        provinces = self.env['account.analytic.account'].search([('parent_id', '=', False), ('plan_id.name', '=', 'Location')])
        if restriction and restriction['provinces']:
            provinces = provinces.browse(restriction['provinces'])

        cities = self.env['account.analytic.account'].search([('parent_id', 'in', provinces.ids)])
        zones = self.env['account.analytic.account'].search([('parent_id', 'in', cities.ids)])
        
        bunches = self.env['key.bunch'].search([])
        schedule_days = self.env['rider.schedule.day'].search([('zone_id', '!=', False), ('key_bunch_id', '!=', False)])
        
        # Apply restriction to Bunches
        if restriction and restriction['analytic_ids']:
            allowed_ids = restriction['analytic_ids']
            allowed_zones = self.env['account.analytic.account'].search([('id', 'child_of', allowed_ids)])
            schedule_days = schedule_days.filtered(lambda sd: sd.zone_id.id in allowed_zones.ids)

        bunch_zone_map = {sd.key_bunch_id.id: sd.zone_id.id for sd in schedule_days}
        bunch_data = [{'id': b.id, 'name': b.name, 'zone_id': bunch_zone_map.get(b.id, False)} for b in bunches if b.id in bunch_zone_map]
        
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
            
        # --- Dashboard Configurator Restriction ---
        restriction = self.env['dashboard.configurator'].get_user_restrictions('donation_box')
        restriction_reg_dom = []
        restriction_col_dom = []
        if restriction and restriction['analytic_ids']:
            allowed_ids = restriction['analytic_ids']
            restriction_reg_dom = ['|', ('city_id', 'child_of', allowed_ids), ('zone_id', 'child_of', allowed_ids)]
            restriction_col_dom = ['|', ('donation_box_registration_installation_id.city_id', 'child_of', allowed_ids), ('donation_box_registration_installation_id.zone_id', 'child_of', allowed_ids)]
            reg_domain.extend(restriction_reg_dom)
            comp_domain.extend(restriction_col_dom)
            col_domain.extend(restriction_col_dom)
        # ------------------------------------------

        # --- Registration domain (direct fields) ---
        reg_location_domain = []
        if province_id:
            reg_location_domain.append(('city_id.parent_id', '=', int(province_id)))
        if city_id:
            reg_location_domain.append(('city_id', '=', int(city_id)))
        if zone_id:
            reg_location_domain.append(('zone_id', '=', int(zone_id)))
        if bunch_id:
            reg_location_domain.append(('key_bunch_id', '=', int(bunch_id)))

        # --- Collection domain (through registration) ---
        col_location_domain = []
        if province_id:
            col_location_domain.append(('donation_box_registration_installation_id.city_id.parent_id', '=', int(province_id)))
        if city_id:
            col_location_domain.append(('donation_box_registration_installation_id.city_id', '=', int(city_id)))
        if zone_id:
            col_location_domain.append(('donation_box_registration_installation_id.zone_id', '=', int(zone_id)))
        if bunch_id:
            col_location_domain.append(('donation_box_registration_installation_id.key_bunch_id', '=', int(bunch_id)))

        # --- Complaint domain (through registration) ---
        comp_location_domain = list(col_location_domain)

        # Apply
        reg_domain.extend(reg_location_domain)
        comp_domain.extend(comp_location_domain)
        col_domain.extend(col_location_domain)
            
        col_domain = list(base_col_domain)
        if date_from: col_domain.append(('date', '>=', date_from))
        if date_to: col_domain.append(('date', '<=', date_to))
        if restriction and restriction['analytic_ids']:
            col_domain.extend(restriction_col_dom)

        Registration = self.env['donation.box.registration.installation']
        Complain = self.env['donation.box.complain.center']
        Collection = self.env['rider.collection']

        # one grouped query per model instead of one count per status
        reg_by_status = dict(Registration._read_group(reg_domain, ['status'], ['__count']))
        draft_boxes = reg_by_status.get('draft', 0)
        available = reg_by_status.get('available', 0)
        installed = reg_by_status.get('installed', 0)
        closed = reg_by_status.get('close', 0)

        comp_by_status = dict(Complain._read_group(comp_domain, ['status'], ['__count']))
        draft_complaints = comp_by_status.get('draft', 0)
        process_complaints = comp_by_status.get('process', 0)
        resolved_complaints = comp_by_status.get('resolved', 0)

        col_by_state = {state: (count, amount) for state, count, amount in
                        Collection._read_group(col_domain, ['state'], ['__count', 'amount:sum'])}
        total_collection = sum(col_by_state.get(state, (0, 0.0))[1] for state in ('donation_submit', 'pending', 'paid'))
        not_collected_count = col_by_state.get('donation_not_collected', (0, 0.0))[0]
        pending_count = col_by_state.get('pending', (0, 0.0))[0]
        paid_count = col_by_state.get('paid', (0, 0.0))[0]

        today = date.today()
        start_3m = (today - relativedelta(months=2)).replace(day=1)
        end_3m = today
        
        start_prev_3m = (start_3m - relativedelta(months=3)).replace(day=1)
        end_prev_3m = start_3m - relativedelta(days=1)

        def collected(start, end):
            [(amount,)] = Collection._read_group(base_col_domain + restriction_col_dom + [
                ('date', '>=', start.strftime('%Y-%m-%d')), ('date', '<=', end.strftime('%Y-%m-%d')),
                ('state', 'in', ['donation_submit', 'pending', 'paid']),
            ], [], ['amount:sum'])
            return amount or 0.0

        current_3m_sum = collected(start_3m, end_3m)
        prev_3m_sum = collected(start_prev_3m, end_prev_3m)

        diff_pct = 0
        if prev_3m_sum > 0:
            diff_pct = ((current_3m_sum - prev_3m_sum) / prev_3m_sum) * 100
        elif current_3m_sum > 0:
            diff_pct = 100

        today_chart = date.today()
        first_month = (today_chart - relativedelta(months=5)).replace(day=1)
        installs = dict(
            (month.strftime('%b %Y'), count) for month, count in Registration._read_group(
                reg_domain + [('installation_date', '>=', first_month.strftime('%Y-%m-%d')),
                              ('installation_date', '<=', today_chart.strftime('%Y-%m-%d'))],
                ['installation_date:month'], ['__count']) if month)
        months = [(today_chart - relativedelta(months=i)).strftime('%b %Y') for i in range(5, -1, -1)]
        counts = [installs.get(month, 0) for month in months]

        installs_by_month = {'labels': months, 'data': counts}

        comp_by_box_status = {}
        comps = Complain.read_group(comp_domain, ['box_status'], ['box_status'])
        for c in comps:
            if c['box_status']:
                comp_by_box_status[c['box_status']] = c['box_status_count']

        # --- Tables ---
        recent_complaints = Complain.search_read(comp_domain, ['lot_id', 'shop_name', 'box_status', 'status', 'date'], limit=10, order='id desc')
        
        recent_registrations = Registration.search_read(
            reg_domain, 
            ['name', 'donor_id', 'installer_id', 'location', 'contact_person', 'contact_no', 'lot_id', 'lock_no', 'box_status', 'installation_date', 'status'], 
            limit=10, order='id desc'
        )
        
        recent_collections = Collection.search_read(col_domain, ['date', 'shop_name', 'rider_id', 'lot_id', 'amount', 'state'], limit=10, order='id desc')

        for c in recent_complaints:
            c['lot_name'] = c['lot_id'][1] if c['lot_id'] else '-'
            c['shop_name'] = c['shop_name'] or '-'
            
        for r in recent_registrations:
            r['donor_name'] = r['donor_id'][1] if r.get('donor_id') else '-'
            r['installer_name'] = r['installer_id'][1] if r.get('installer_id') else '-'
            r['lot_name'] = r['lot_id'][1] if r.get('lot_id') else '-'
            r['reg_name'] = r.get('name') or '-'
            r['location'] = r.get('location') or '-'
            r['contact_person'] = r.get('contact_person') or '-'
            r['contact_no'] = r.get('contact_no') or '-'
            r['lock_no'] = r.get('lock_no') or '-'
            r['box_status'] = r.get('box_status') or '-'
            r['installation_date'] = r.get('installation_date') or '-'
            r['status'] = r.get('status') or '-'

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
    def get_comparison_data(self, mode='month', period1=None, period2=None,
                            province_id=None, city_id=None, zone_id=None, bunch_id=None):
        empty = {'p1': {}, 'p2': {}, 'diffs': {}, 'mode': mode, 'period1': period1, 'period2': period2}

        def _parse(period_str):
            if not period_str: return None, None
            try:
                if mode == 'month':
                    year, month = map(int, str(period_str).split('-'))
                    start = date(year, month, 1)
                    end = date(year, month, calendar.monthrange(year, month)[1])
                else:
                    year = int(period_str)
                    start = date(year, 1, 1)
                    end = date(year, 12, 31)
            except (ValueError, TypeError): return None, None
            return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')

        p1_start, p1_end = _parse(period1)
        p2_start, p2_end = _parse(period2)

        if not p1_start or not p2_start: return empty

        # --- Base domains ---
        col_base = []
        if province_id: col_base.append(('donation_box_registration_installation_id.city_id.parent_id', '=', int(province_id)))
        if city_id: col_base.append(('donation_box_registration_installation_id.city_id', '=', int(city_id)))
        if zone_id: col_base.append(('donation_box_registration_installation_id.zone_id', '=', int(zone_id)))
        if bunch_id: col_base.append(('donation_box_registration_installation_id.key_bunch_id', '=', int(bunch_id)))

        reg_base = []
        if province_id: reg_base.append(('city_id.parent_id', '=', int(province_id)))
        if city_id: reg_base.append(('city_id', '=', int(city_id)))
        if zone_id: reg_base.append(('zone_id', '=', int(zone_id)))
        if bunch_id: reg_base.append(('key_bunch_id', '=', int(bunch_id)))

        # --- Configurator Restriction ---
        restriction = self.env['dashboard.configurator'].get_user_restrictions('donation_box')
        if restriction and restriction['analytic_ids']:
            allowed_ids = restriction['analytic_ids']
            col_base.extend(['|', ('donation_box_registration_installation_id.city_id', 'child_of', allowed_ids), ('donation_box_registration_installation_id.zone_id', 'child_of', allowed_ids)])
            reg_base.extend(['|', ('city_id', 'child_of', allowed_ids), ('zone_id', 'child_of', allowed_ids)])
        # -------------------------------

        Collection = self.env['rider.collection']
        Registration = self.env['donation.box.registration.installation']
        Complaint = self.env['donation.box.complain.center']

        def _collect(start, end):
            cols = Collection.search(col_base + [('date', '>=', start), ('date', '<=', end), ('state', 'in', ['donation_submit', 'pending', 'paid'])])
            return {'collection_amount': sum(cols.mapped('amount')), 'collection_count': len(cols)}

        def _registrations(start, end):
            return Registration.search_count(reg_base + [('installation_date', '>=', start), ('installation_date', '<=', end)])

        def _complaints(start, end):
            return Complaint.search_count(col_base + [('date', '>=', start), ('date', '<=', end)])

        p1_data = _collect(p1_start, p1_end)
        p2_data = _collect(p2_start, p2_end)

        p1 = {'collection_amount': p1_data['collection_amount'], 'collection_count': p1_data['collection_count'], 'installations': _registrations(p1_start, p1_end), 'complaints': _complaints(p1_start, p1_end)}
        p2 = {'collection_amount': p2_data['collection_amount'], 'collection_count': p2_data['collection_count'], 'installations': _registrations(p2_start, p2_end), 'complaints': _complaints(p2_start, p2_end)}

        diffs = {}
        for key in p1:
            v1, v2 = p1[key], p2[key]
            diff = v2 - v1
            pct = (diff / v1 * 100) if v1 > 0 else (100.0 if v2 > 0 else 0.0)
            diffs[key] = {'diff': diff, 'pct': pct, 'is_positive': diff >= 0}

        return {'p1': p1, 'p2': p2, 'diffs': diffs, 'mode': mode, 'period1': period1, 'period2': period2}