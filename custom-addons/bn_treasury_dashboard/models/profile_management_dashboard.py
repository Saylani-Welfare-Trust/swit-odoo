# -*- coding: utf-8 -*-
from odoo import api, models

class ProfileManagementDashboard(models.TransientModel):
    _name = 'profile.management.dashboard'
    _description = 'Profile Management Dashboard'

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None):
        domain = []
        
        if date_from:
            domain.append(('create_date', '>=', date_from + ' 00:00:00'))
        if date_to:
            domain.append(('create_date', '<=', date_to + ' 23:59:59'))

        Partner = self.env['res.partner']

        # --- KPIs ---
        registered = Partner.search_count(domain + [('state', '=', 'register')])
        draft = Partner.search_count(domain + [('state', '=', 'draft')])
        rejected = Partner.search_count(domain + [('state', '=', 'reject')])
        
        donors = Partner.search_count(domain + [('category_id.name', 'ilike', 'Donor')])
        donees = Partner.search_count(domain + [('category_id.name', 'ilike', 'Donee')])
        individuals = Partner.search_count(domain + [('category_id.name', 'ilike', 'Individual')])

        # --- Charts ---
        regs_by_month = {}
        regs = Partner.read_group(domain, ['create_date'], ['create_date:month'])
        for r in regs:
            if r['create_date:month']:
                regs_by_month[r['create_date:month']] = r['create_date_count']

        cat_dist = {}
        cats = Partner.read_group(domain, ['category_id'], ['category_id'])
        for c in cats:
            if c['category_id']:
                cat_dist[c['category_id'][1]] = c['category_id_count']

        # --- Tables ---
        recent_registrations = Partner.search_read(
            domain + [('state', '=', 'register')],
            ['name', 'mobile', 'cnic_no', 'category_id', 'create_date'],
            limit=10, order='create_date desc'
        )
        
        recent_drafts = Partner.search_read(
            domain + [('state', '=', 'draft')],
            ['name', 'mobile', 'cnic_no', 'category_id', 'create_date'],
            limit=10, order='create_date desc'
        )

        # --- Partner Details (Tabs) ---
        partners = Partner.search(domain)
        partner_ids = partners.ids
        
        recent_pos_orders = []
        recent_boxes = []
        
        if partner_ids:
            # POS Details
            pos_domain = [('partner_id', 'in', partner_ids)]
            if date_from: pos_domain.append(('date_order', '>=', date_from + ' 00:00:00'))
            if date_to: pos_domain.append(('date_order', '<=', date_to + ' 23:59:59'))
            
            recent_pos_orders = self.env['pos.order'].search_read(
                pos_domain,
                ['name', 'date_order', 'amount_total', 'state'],
                limit=10, order='date_order desc'
            )

            # Box Details
            box_domain = [('donor_id', 'in', partner_ids)]
            if date_from: box_domain.append(('installation_date', '>=', date_from))
            if date_to: box_domain.append(('installation_date', '<=', date_to))

            recent_boxes = self.env['donation.box.registration.installation'].search_read(
                box_domain,
                ['name', 'lot_id', 'status', 'installation_date'],
                limit=10, order='installation_date desc'
            )

        return {
            'kpi': {
                'registered': registered,
                'draft': draft,
                'rejected': rejected,
                'donors': donors,
                'donees': donees,
                'individuals': individuals,
            },
            'chart_regs': {
                'labels': list(regs_by_month.keys()),
                'data': list(regs_by_month.values()),
            },
            'chart_cats': {
                'labels': list(cat_dist.keys()),
                'data': list(cat_dist.values()),
            },
            'recent_registrations': recent_registrations,
            'recent_drafts': recent_drafts,
            'recent_pos_orders': recent_pos_orders,
            'recent_boxes': recent_boxes,
        }