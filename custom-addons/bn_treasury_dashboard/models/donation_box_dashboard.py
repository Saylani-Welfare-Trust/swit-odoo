# -*- coding: utf-8 -*-
from odoo import api, models
from datetime import datetime

class DonationBoxDashboard(models.AbstractModel):
    _name = 'donation.box.dashboard'
    _description = 'Donation Box Dashboard'

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None):
        reg_domain = []
        comp_domain = []
        
        if date_from:
            reg_domain.append(('installation_date', '>=', date_from))
            comp_domain.append(('date', '>=', date_from))
        if date_to:
            reg_domain.append(('installation_date', '<=', date_to))
            comp_domain.append(('date', '<=', date_to))

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
        # 1. Complaints by Box Status
        comp_by_box_status = {}
        comps = Complain.read_group(comp_domain, ['box_status'], ['box_status'])
        for c in comps:
            if c['box_status']:
                comp_by_box_status[c['box_status']] = c['box_status_count']

        # 2. Installations by Month
        installs_by_month = {}
        # Using read_group to group by installation_date (month)
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

        # Format M2O fields for the frontend
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