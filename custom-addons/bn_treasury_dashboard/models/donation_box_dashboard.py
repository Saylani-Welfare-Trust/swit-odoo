# -*- coding: utf-8 -*-
from odoo import api, models

class DonationBoxDashboard(models.AbstractModel):
    _name = 'donation.box.dashboard'
    _description = 'Donation Box Dashboard'

    @api.model
    def get_location_hierarchy(self):
        # Location Hierarchy
        provinces = self.env['account.analytic.account'].search([('parent_id', '=', False), ('plan_id.name', '=', 'Location')])
        cities = self.env['account.analytic.account'].search([('parent_id', 'in', provinces.ids)])
        zones = self.env['account.analytic.account'].search([('parent_id', 'in', cities.ids)])
        
        # Segment Hierarchy (4 Levels)
        seg_l1 = self.env['account.analytic.account'].search([('parent_id', '=', False), ('plan_id.name', 'ilike', 'Segment')])
        seg_l2 = self.env['account.analytic.account'].search([('parent_id', 'in', seg_l1.ids)])
        seg_l3 = self.env['account.analytic.account'].search([('parent_id', 'in', seg_l2.ids)])
        seg_l4 = self.env['account.analytic.account'].search([('parent_id', 'in', seg_l3.ids)])
        
        return {
            'provinces': [{'id': p.id, 'name': p.name} for p in provinces],
            'cities': [{'id': c.id, 'name': c.name, 'province_id': c.parent_id.id} for c in cities],
            'zones': [{'id': z.id, 'name': z.name, 'city_id': z.parent_id.id} for z in zones],
            'segments_l1': [{'id': s.id, 'name': s.name} for s in seg_l1],
            'segments_l2': [{'id': s.id, 'name': s.name, 'parent_id': s.parent_id.id} for s in seg_l2],
            'segments_l3': [{'id': s.id, 'name': s.name, 'parent_id': s.parent_id.id} for s in seg_l3],
            'segments_l4': [{'id': s.id, 'name': s.name, 'parent_id': s.parent_id.id} for s in seg_l4],
        }

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None, 
                           province_id=None, city_id=None, zone_id=None,
                           segment_l1=None, segment_l2=None, segment_l3=None, segment_l4=None, 
                           segment_type=None):
        reg_domain = []
        comp_domain = []
        
        if date_from:
            reg_domain.append(('installation_date', '>=', date_from))
            comp_domain.append(('date', '>=', date_from))
        if date_to:
            reg_domain.append(('installation_date', '<=', date_to))
            comp_domain.append(('date', '<=', date_to))
            
        # Location Filters
        if province_id:
            reg_domain.append(('city_id.parent_id', '=', int(province_id)))
            comp_domain.append(('city_id.parent_id', '=', int(province_id)))
        if city_id:
            reg_domain.append(('city_id', '=', int(city_id)))
            comp_domain.append(('city_id', '=', int(city_id)))
        if zone_id:
            reg_domain.append(('zone_id', '=', int(zone_id)))
            comp_domain.append(('zone_id', '=', int(zone_id)))
            
        # Segment Filters
        effective_segment_id = segment_l4 or segment_l3 or segment_l2 or segment_l1
        if effective_segment_id:
            # If your model has a segment field or analytic account, filter by it
            if 'segment_id' in self.env['donation.box.registration.installation']._fields:
                reg_domain.append(('segment_id', 'child_of', int(effective_segment_id)))
                comp_domain.append(('segment_id', 'child_of', int(effective_segment_id)))
            elif 'analytic_account_id' in self.env['donation.box.registration.installation']._fields:
                reg_domain.append(('analytic_account_id', 'child_of', int(effective_segment_id)))
                comp_domain.append(('analytic_account_id', 'child_of', int(effective_segment_id)))
                
        if segment_type:
            # If your model has a field to filter by (N) or (W)
            if 'segment_type' in self.env['donation.box.registration.installation']._fields:
                reg_domain.append(('segment_type', '=', segment_type))
                comp_domain.append(('segment_type', '=', segment_type))
            elif 'name' in self.env['donation.box.registration.installation']._fields:
                reg_domain.append(('name', 'ilike', f'%({segment_type})%'))
                comp_domain.append(('name', 'ilike', f'%({segment_type})%'))

        Registration = self.env['donation.box.registration.installation']
        Complain = self.env['donation.box.complain.center']

        # --- KPIs ---
        available = Registration.search_count(reg_domain + [('status', '=', 'available')])
        installed = Registration.search_count(reg_domain + [('status', '=', 'installed')])
        closed = Registration.search_count(reg_domain + [('status', '=', 'close')])
        
        active_complaints = Complain.search_count(comp_domain + [('status', 'in', ['draft', 'process'])])
        resolved_complaints = Complain.search_count(comp_domain + [('status', '=', 'resolved')])
        not_recovered = Complain.search_count(comp_domain + [('status', '=', 'not_recovered')])

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