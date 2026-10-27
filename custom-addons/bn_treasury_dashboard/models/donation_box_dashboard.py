# -*- coding: utf-8 -*-
from odoo import api, models

class DonationBoxDashboard(models.TransientModel):
    _name = 'donation.box.dashboard'
    _description = 'Donation Box Dashboard'

    @api.model
    def get_location_hierarchy(self):
        provinces = self.env['account.analytic.account'].search([('parent_id', '=', False), ('plan_id.name', '=', 'Location')])
        cities = self.env['account.analytic.account'].search([('parent_id', 'in', provinces.ids)])
        
        # 1. Fetch Subzones and map to City
        subzones = self.env['sub.zone'].search([])
        subzone_data = []
        for s in subzones:
            city_id = False
            if 'city_id' in s._fields and s.city_id:
                city_id = s.city_id.id
            elif 'zone_id' in s._fields and s.zone_id and s.zone_id.parent_id:
                city_id = s.zone_id.parent_id.id
            
            subzone_data.append({'id': s.id, 'name': s.name, 'city_id': city_id})
            
        # 2. Fetch Bunches and map to Subzone
        bunches = self.env['key.bunch'].search([])
        bunch_data = []
        for b in bunches:
            subzone_id = False
            if 'sub_zone_id' in b._fields and b.sub_zone_id:
                subzone_id = b.sub_zone_id.id
            else:
                # Fallback: match subzone name in bunch name (e.g., "BAHADURABAD" in "BAHADURABAD 1 - CB 1")
                for sz in subzones:
                    if sz.name and sz.name.strip() in b.name:
                        subzone_id = sz.id
                        break
            bunch_data.append({'id': b.id, 'name': b.name, 'subzone_id': subzone_id})
            
        return {
            'provinces': [{'id': p.id, 'name': p.name} for p in provinces],
            'cities': [{'id': c.id, 'name': c.name, 'province_id': c.parent_id.id} for c in cities],
            'subzones': subzone_data,
            'bunches': bunch_data,
        }

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None, 
                           province_id=None, city_id=None, subzone_id=None, bunch_id=None):
        reg_domain = []
        comp_domain = []
        col_domain = []
        
        # Date Filters
        if date_from:
            reg_domain.append(('installation_date', '>=', date_from))
            comp_domain.append(('date', '>=', date_from))
            col_domain.append(('date', '>=', date_from))
        if date_to:
            reg_domain.append(('installation_date', '<=', date_to))
            comp_domain.append(('date', '<=', date_to))
            col_domain.append(('date', '<=', date_to))
            
        # Location Filters
        if province_id:
            reg_domain.append(('city_id.parent_id', '=', int(province_id)))
            comp_domain.append(('city_id.parent_id', '=', int(province_id)))
            col_domain.append(('donation_box_registration_installation_id.city_id.parent_id', '=', int(province_id)))
        if city_id:
            reg_domain.append(('city_id', '=', int(city_id)))
            comp_domain.append(('city_id', '=', int(city_id)))
            col_domain.append(('donation_box_registration_installation_id.city_id', '=', int(city_id)))
        if subzone_id:
            reg_domain.append(('sub_zone_id', '=', int(subzone_id)))
            comp_domain.append(('donation_box_registration_installation_id.sub_zone_id', '=', int(subzone_id)))
            col_domain.append(('donation_box_registration_installation_id.sub_zone_id', '=', int(subzone_id)))
        if bunch_id:
            reg_domain.append(('key_bunch_id', '=', int(bunch_id)))
            comp_domain.append(('donation_box_registration_installation_id.key_bunch_id', '=', int(bunch_id)))
            col_domain.append(('donation_box_registration_installation_id.key_bunch_id', '=', int(bunch_id)))

        Registration = self.env['donation.box.registration.installation']
        Complain = self.env['donation.box.complain.center']
        Collection = self.env['rider.collection']

        # --- Box KPIs ---
        draft_boxes = Registration.search_count(reg_domain + [('status', '=', 'draft')])
        available = Registration.search_count(reg_domain + [('status', '=', 'available')])
        installed = Registration.search_count(reg_domain + [('status', '=', 'installed')])
        closed = Registration.search_count(reg_domain + [('status', '=', 'close')])
        
        # --- Complaint KPIs ---
        draft_complaints = Complain.search_count(comp_domain + [('status', '=', 'draft')])
        process_complaints = Complain.search_count(comp_domain + [('status', '=', 'process')])
        resolved_complaints = Complain.search_count(comp_domain + [('status', '=', 'resolved')])

        # --- Collection KPIs ---
        collections = Collection.search(col_domain)
        total_collection = 0.0
        
        for col in collections:
            if col.state in ['donation_submit', 'pending', 'paid']:
                total_collection += col.amount or 0.0

        not_collected_count = Collection.search_count(col_domain + [('state', '=', 'donation_not_collected')])
        pending_count = Collection.search_count(col_domain + [('state', '=', 'pending')])
        paid_count = Collection.search_count(col_domain + [('state', '=', 'paid')])

        # --- Charts ---
        comp_by_box_status = {}
        comps = Complain.read_group(comp_domain, ['box_status'], ['box_status'])
        for c in comps:
            if c['box_status']:
                comp_by_box_status[c['box_status']] = c['box_status_count']

        installs_by_month = {}
        regs = Registration.read_group(
            reg_domain + [('installation_date', '!=', False)], 
            ['installation_date'], 
            ['installation_date:month']
        )
        for r in regs:
            if r['installation_date:month']:
                installs_by_month[r['installation_date:month']] = r['installation_date_count']

        # --- Tables ---
        recent_complaints = Complain.search_read(
            comp_domain, 
            ['lot_id', 'shop_name', 'box_status', 'status', 'date'], 
            limit=10, order='id desc'
        )
        
        recent_registrations = Registration.search_read(
            reg_domain, 
            ['shop_name', 'lot_id', 'city_id', 'installation_date', 'status'], 
            limit=10, order='id desc'
        )
        
        recent_collections = Collection.search_read(
            col_domain,
            ['date', 'shop_name', 'rider_id', 'lot_id', 'amount', 'state'],
            limit=10, order='id desc'
        )

        for c in recent_complaints:
            c['lot_name'] = c['lot_id'][1] if c['lot_id'] else ''
        for r in recent_registrations:
            r['lot_name'] = r['lot_id'][1] if r['lot_id'] else ''
            r['city_name'] = r['city_id'][1] if r['city_id'] else ''
        for col in recent_collections:
            col['rider_name'] = col['rider_id'][1] if col['rider_id'] else ''
            col['lot_name'] = col['lot_id'][1] if col['lot_id'] else ''

        return {
            'kpi': {
                'draft_boxes': draft_boxes,
                'available': available,
                'installed': installed,
                'closed': closed,
                'draft_complaints': draft_complaints,
                'process_complaints': process_complaints,
                'resolved_complaints': resolved_complaints,
                'total_collection': "{:,.2f}".format(total_collection),
                'not_collected_count': not_collected_count,
                'pending_count': pending_count,
                'paid_count': paid_count,
            },
            'chart_comp_status': {
                'labels': list(comp_by_box_status.keys()),
                'data': list(comp_by_box_status.values()),
            },
            'chart_installs': {
                'labels': list(installs_by_month.keys()),
                'data': list(installs_by_month.values()),
            },
            'recent_complaints': recent_complaints,
            'recent_registrations': recent_registrations,
            'recent_collections': recent_collections,
        }