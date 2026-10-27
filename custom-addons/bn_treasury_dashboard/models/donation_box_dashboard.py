# -*- coding: utf-8 -*-
from odoo import api, models

class DonationBoxDashboard(models.TransientModel): # Changed from AbstractModel to TransientModel
    _name = 'donation.box.dashboard'
    _description = 'Donation Box Dashboard'

    @api.model
    def get_location_hierarchy(self):
        # Location Hierarchy: Province -> City -> Zone -> Branch
        provinces = self.env['account.analytic.account'].search([('parent_id', '=', False), ('plan_id.name', '=', 'Location')])
        cities = self.env['account.analytic.account'].search([('parent_id', 'in', provinces.ids)])
        zones = self.env['account.analytic.account'].search([('parent_id', 'in', cities.ids)])
        branches = self.env['account.analytic.account'].search([('parent_id', 'in', zones.ids)])
        
        return {
            'provinces': [{'id': p.id, 'name': p.name} for p in provinces],
            'cities': [{'id': c.id, 'name': c.name, 'province_id': c.parent_id.id} for c in cities],
            'zones': [{'id': z.id, 'name': z.name, 'city_id': z.parent_id.id} for z in zones],
            'branches': [{'id': b.id, 'name': b.name, 'zone_id': b.parent_id.id} for b in branches],
        }

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None, 
                           province_id=None, city_id=None, zone_id=None, branch_id=None):
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
        if zone_id:
            reg_domain.append(('zone_id', '=', int(zone_id)))
            comp_domain.append(('zone_id', '=', int(zone_id)))
            col_domain.append(('donation_box_registration_installation_id.zone_id', '=', int(zone_id)))
        if branch_id:
            if 'sub_zone_id' in self.env['donation.box.registration.installation']._fields:
                reg_domain.append(('sub_zone_id', '=', int(branch_id)))
                comp_domain.append(('sub_zone_id', '=', int(branch_id)))
                col_domain.append(('donation_box_registration_installation_id.sub_zone_id', '=', int(branch_id)))

        Registration = self.env['donation.box.registration.installation']
        Complain = self.env['donation.box.complain.center']
        Collection = self.env['rider.collection']

        # --- Box KPIs ---
        available = Registration.search_count(reg_domain + [('status', '=', 'available')])
        installed = Registration.search_count(reg_domain + [('status', '=', 'installed')])
        closed = Registration.search_count(reg_domain + [('status', '=', 'close')])
        
        # --- Complaint KPIs ---
        active_complaints = Complain.search_count(comp_domain + [('status', 'in', ['draft', 'process'])])
        resolved_complaints = Complain.search_count(comp_domain + [('status', '=', 'resolved')])
        not_recovered = Complain.search_count(comp_domain + [('status', '=', 'not_recovered')])

        # --- Collection KPIs ---
        collections = Collection.search(col_domain)
        total_collection = 0.0
        rider_collection = 0.0
        visit_collection = 0.0
        
        for col in collections:
            # Total Collection: All valid submissions
            if col.state in ['donation_submit', 'pending', 'paid']:
                total_collection += col.amount or 0.0
            
            # Rider Collection: Standard Cash (excluding FCB/CFB)
            if col.remarks not in ['FCB', 'CFB']:
                rider_collection += col.amount or 0.0
                
            # Visit Collection: Fully Paid collections
            if col.state == 'paid':
                visit_collection += col.amount or 0.0

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

        for c in recent_complaints:
            c['lot_name'] = c['lot_id'][1] if c['lot_id'] else ''
        for r in recent_registrations:
            r['lot_name'] = r['lot_id'][1] if r['lot_id'] else ''
            r['city_name'] = r['city_id'][1] if r['city_id'] else ''

        return {
            'kpi': {
                'available': available,
                'installed': installed,
                'closed': closed,
                'active_complaints': active_complaints,
                'resolved_complaints': resolved_complaints,
                'not_recovered': not_recovered,
                'total_collection': "{:,.2f}".format(total_collection),
                'rider_collection': "{:,.2f}".format(rider_collection),
                'visit_collection': "{:,.2f}".format(visit_collection),
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
        }