# -*- coding: utf-8 -*-
from odoo import api, models
import logging

_logger = logging.getLogger(__name__)

class ProfileManagementDashboard(models.TransientModel):
    _name = 'profile.management.dashboard'
    _description = 'Profile Management Dashboard'

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None):
        try:
            return self._get_dashboard_data(date_from, date_to)
        except Exception as e:
            _logger.error(f"Dashboard Critical Error: {e}", exc_info=True)
            return {
                'kpi': {'registered': 0, 'draft': 0, 'rejected': 0, 'donors': 0, 'donees': 0, 'individuals': 0},
                'chart_regs': {'labels': [], 'data': []},
                'chart_cats': {'labels': [], 'data': []},
                'recent_registrations': [],
                'recent_drafts': [],
                'pos_orders': [], 'boxes': [], 'home_services': [], 'imports': [], 'online': [], 'in_kind': []
            }

    def _get_dashboard_data(self, date_from, date_to):
        domain = []
        
        if date_from:
            domain.append(('create_date', '>=', date_from + ' 00:00:00'))
        if date_to:
            domain.append(('create_date', '<=', date_to + ' 23:59:59'))

        Partner = self.env['res.partner']
        
        def safe_count(model, dom):
            try:
                return model.search_count(dom)
            except Exception as e:
                _logger.error(f"Dashboard Error on {model._name}: {e}")
                return 0

        def safe_search_read(model, dom, fields, limit=10, order='id desc'):
            try:
                valid_fields = [f for f in fields if f in model._fields]
                if not valid_fields:
                    return []
                return model.search_read(dom, valid_fields, limit=limit, order=order)
            except Exception as e:
                _logger.error(f"Dashboard Error on {model._name}: {e}")
                return []

        # --- KPIs ---
        registered = safe_count(Partner, domain + [('state', '=', 'register')])
        draft = safe_count(Partner, domain + [('state', '=', 'draft')])
        rejected = safe_count(Partner, domain + [('state', '=', 'reject')])
        
        donors = safe_count(Partner, domain + [('category_id.name', 'ilike', 'Donor')])
        donees = safe_count(Partner, domain + [('category_id.name', 'ilike', 'Donee')])
        individuals = safe_count(Partner, domain + [('category_id.name', 'ilike', 'Individual')])

        # --- Charts ---
        regs_by_month = {}
        try:
            regs = Partner.read_group(domain, ['create_date'], ['create_date:month'])
            for r in regs:
                if r['create_date:month']:
                    regs_by_month[r['create_date:month']] = r['create_date_count']
        except Exception:
            pass

        cat_dist = {}
        try:
            cats = Partner.read_group(domain, ['category_id'], ['category_id'])
            for c in cats:
                if c['category_id']:
                    cat_dist[c['category_id'][1]] = c['category_id_count']
        except Exception:
            pass

        # --- Tables (Top 2) ---
        recent_registrations = safe_search_read(
            Partner, domain + [('state', '=', 'register')],
            ['name', 'mobile', 'cnic_no', 'category_id', 'create_date']
        )
        
        recent_drafts = safe_search_read(
            Partner, domain + [('state', '=', 'draft')],
            ['name', 'mobile', 'cnic_no', 'category_id', 'create_date']
        )

        # --- Details Tabs ---
        pos_orders, boxes, home_services, imports, online, in_kind = [], [], [], [], [], []
        
        partners = Partner.search(domain, limit=5000)
        partner_ids = partners.ids

        if partner_ids:
            # 1. POS Details
            if 'pos.order' in self.env:
                pos_domain = [('partner_id', 'in', partner_ids)]
                if date_from: pos_domain.append(('date_order', '>=', date_from + ' 00:00:00'))
                if date_to: pos_domain.append(('date_order', '<=', date_to + ' 23:59:59'))
                pos_orders = safe_search_read(
                    self.env['pos.order'], pos_domain, ['name', 'date_order', 'amount_total', 'state'], order='date_order desc'
                )

            # 2. Box Details
            if 'donation.box.registration.installation' in self.env:
                box_domain = [('donor_id', 'in', partner_ids)]
                if date_from: box_domain.append(('installation_date', '>=', date_from))
                if date_to: box_domain.append(('installation_date', '<=', date_to))
                boxes = safe_search_read(
                    self.env['donation.box.registration.installation'], box_domain, ['name', 'lot_id', 'status', 'installation_date'], order='installation_date desc'
                )

            # =========================================================================
            # 3. Home Service Details (Mapped to donation.home.service)
            # =========================================================================
            if 'donation.home.service' in self.env:
                hs_domain = [('donor_id', 'in', partner_ids)]
                if date_from: hs_domain.append(('create_date', '>=', date_from + ' 00:00:00'))
                if date_to: hs_domain.append(('create_date', '<=', date_to + ' 23:59:59'))
                
                home_services = safe_search_read(
                    self.env['donation.home.service'], hs_domain, ['name', 'create_date', 'total_amount', 'state'], order='create_date desc'
                )
                # Map fields to match UI
                for hs in home_services:
                    date_val = hs.get('create_date')
                    hs['date'] = str(date_val).split(' ')[0] if date_val else '-'
                    hs['amount'] = hs.get('total_amount', 0.0)

            # =========================================================================
            # 4. Import Details
            # =========================================================================
            if 'donation' in self.env:
                imp_domain = [('donor_id', 'in', partner_ids), ('import_donation_id', '!=', False)]
                if date_from: imp_domain.append(('create_date', '>=', date_from + ' 00:00:00'))
                if date_to: imp_domain.append(('create_date', '<=', date_to + ' 23:59:59'))
                
                imports = safe_search_read(
                    self.env['donation'], imp_domain, ['name', 'create_date', 'amount', 'state'], order='create_date desc'
                )
                for imp in imports:
                    date_val = imp.get('create_date')
                    imp['date'] = str(date_val).split(' ')[0] if date_val else '-'
                    imp['state'] = imp.get('state', 'draft')

            # =========================================================================
            # 5. Online Details
            # =========================================================================
            if 'api.donation' in self.env:
                on_domain = [('donor_id', 'in', partner_ids)]
                if date_from: on_domain.append(('created_at', '>=', date_from + ' 00:00:00'))
                if date_to: on_domain.append(('created_at', '<=', date_to + ' 23:59:59'))
                
                online = safe_search_read(
                    self.env['api.donation'], on_domain, ['name', 'created_at', 'total_amount', 'partner_creation_status'], order='created_at desc'
                )
                for on in online:
                    date_val = on.get('created_at')
                    on['date'] = str(date_val).split(' ')[0] if date_val else '-'
                    on['state'] = on.get('partner_creation_status', 'pending')
                    
                    amt_str = str(on.get('total_amount', '0')).replace(',', '')
                    try:
                        on['amount'] = float(amt_str)
                    except ValueError:
                        on['amount'] = 0.0

            # =========================================================================
            # 6. Donation In Kind
            # =========================================================================
            if 'donation.in.kind' in self.env:
                ik_domain = [('donor_id', 'in', partner_ids)]
                if date_from: ik_domain.append(('create_date', '>=', date_from + ' 00:00:00'))
                if date_to: ik_domain.append(('create_date', '<=', date_to + ' 23:59:59'))
                
                ik_records = safe_search_read(
                    self.env['donation.in.kind'], ik_domain, 
                    ['name', 'donor_id', 'state', 'donation_in_kind_line_ids'], 
                    limit=50, order='create_date desc'
                )
                
                for rec in ik_records:
                    lines = self.env['donation.in.kind.line'].search_read(
                        [('donation_in_kind_id', '=', rec['id'])],
                        ['product_id', 'location_id', 'quantity']
                    )
                    for line in lines:
                        in_kind.append({
                            'reference': rec['name'],
                            'donor': rec['donor_id'][1] if rec['donor_id'] else '-',
                            'product': line['product_id'][1] if line['product_id'] else '-',
                            'location': line['location_id'][1] if line['location_id'] else '-',
                            'quantity': line['quantity'],
                            'state': rec['state']
                        })

        return {
            'kpi': {
                'registered': registered, 'draft': draft, 'rejected': rejected,
                'donors': donors, 'donees': donees, 'individuals': individuals,
            },
            'chart_regs': {'labels': list(regs_by_month.keys()), 'data': list(regs_by_month.values())},
            'chart_cats': {'labels': list(cat_dist.keys()), 'data': list(cat_dist.values())},
            'recent_registrations': recent_registrations,
            'recent_drafts': recent_drafts,
            'pos_orders': pos_orders,
            'boxes': boxes,
            'home_services': home_services,
            'imports': imports,
            'online': online,
            'in_kind': in_kind,
        }