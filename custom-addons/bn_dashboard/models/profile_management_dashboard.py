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
                'pos_top_donors': [], 'box_top_donors': [], 'home_top_donors': [], 
                'import_top_donors': [], 'online_top_donors': [], 'in_kind_top_donors': []
            }

    def _get_dashboard_data(self, date_from, date_to):
        domain = []
        if date_from: domain.append(('create_date', '>=', date_from + ' 00:00:00'))
        if date_to: domain.append(('create_date', '<=', date_to + ' 23:59:59'))

        Partner = self.env['res.partner']
        
        def safe_count(model, dom):
            try: return model.search_count(dom)
            except: return 0

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
                if r['create_date:month']: regs_by_month[r['create_date:month']] = r['create_date_count']
        except: pass

        cat_dist = {}
        try:
            cats = Partner.read_group(domain, ['category_id'], ['category_id'])
            for c in cats:
                if c['category_id']: cat_dist[c['category_id'][1]] = c['category_id_count']
        except: pass

        # --- Tables (Recent Top 2) ---
        recent_registrations = Partner.search_read(domain + [('state', '=', 'register')], ['name', 'mobile', 'cnic_no', 'category_id', 'create_date'], limit=10, order='create_date desc')
        recent_drafts = Partner.search_read(domain + [('state', '=', 'draft')], ['name', 'mobile', 'cnic_no', 'category_id', 'create_date'], limit=10, order='create_date desc')

        # =========================================================================
        # TOP 10 DONORS BY AMOUNT (Aggregated)
        # =========================================================================
        
        def get_top_orm(model_name, date_field, partner_field, amount_field):
            if model_name not in self.env: return []
            dom = []
            if date_from: dom.append((date_field, '>=', date_from + ' 00:00:00'))
            if date_to: dom.append((date_field, '<=', date_to + ' 23:59:59'))
            
            try:
                groups = self.env[model_name].read_group(dom, [partner_field, f'{amount_field}:sum'], [partner_field], limit=10, orderby=f'{amount_field} desc')
                res = []
                for g in groups:
                    if g[partner_field]:
                        res.append({
                            'name': g[partner_field][1],
                            'amount': g.get(amount_field, 0.0),
                            'count': g.get('__count', 0)
                        })
                return res
            except Exception as e:
                _logger.error(f"Top 10 Error {model_name}: {e}")
                return []

        # 1. POS
        pos_top_donors = get_top_orm('pos.order', 'date_order', 'partner_id', 'amount_total')
        
        # 2. Box (No amount, grouped by count)
        box_top_donors = []
        if 'donation.box.registration.installation' in self.env:
            box_dom = []
            if date_from: box_dom.append(('installation_date', '>=', date_from))
            if date_to: box_dom.append(('installation_date', '<=', date_to))
            try:
                groups = self.env['donation.box.registration.installation'].read_group(box_dom, ['donor_id'], ['donor_id'], limit=10, orderby='donor_id_count desc')
                for g in groups:
                    if g['donor_id']:
                        box_top_donors.append({'name': g['donor_id'][1], 'amount': 0.0, 'count': g.get('__count', 0)})
            except: pass

        # 3. Home Service
        home_top_donors = get_top_orm('donation.home.service', 'create_date', 'donor_id', 'total_amount')

        # 4. Import Details
        import_top_donors = []
        if 'donation' in self.env:
            imp_dom = [('import_donation_id', '!=', False)]
            if date_from: imp_dom.append(('create_date', '>=', date_from + ' 00:00:00'))
            if date_to: imp_dom.append(('create_date', '<=', date_to + ' 23:59:59'))
            try:
                groups = self.env['donation'].read_group(imp_dom, ['donor_id', 'amount:sum'], ['donor_id'], limit=10, orderby='amount desc')
                for g in groups:
                    if g['donor_id']:
                        import_top_donors.append({'name': g['donor_id'][1], 'amount': g.get('amount', 0.0), 'count': g.get('__count', 0)})
            except: pass

        # 5. Online Details (Aggregating Char field manually)
        online_top_donors = []
        if 'api.donation' in self.env:
            on_dom = []
            if date_from: on_dom.append(('created_at', '>=', date_from + ' 00:00:00'))
            if date_to: on_dom.append(('created_at', '<=', date_to + ' 23:59:59'))
            records = self.env['api.donation'].search(on_dom)
            agg = {}
            for rec in records:
                if not rec.donor_id: continue
                amt_str = str(rec.total_amount or '0').replace(',', '')
                try: amt = float(amt_str)
                except: amt = 0.0
                
                if rec.donor_id.id not in agg:
                    agg[rec.donor_id.id] = {'name': rec.donor_id.name, 'amount': 0.0, 'count': 0}
                agg[rec.donor_id.id]['amount'] += amt
                agg[rec.donor_id.id]['count'] += 1
            online_top_donors = sorted(agg.values(), key=lambda x: x['amount'], reverse=True)[:10]

        # 6. Donation In Kind (Calculating from lines manually)
        in_kind_top_donors = []
        if 'donation.in.kind' in self.env:
            ik_dom = []
            if date_from: ik_dom.append(('create_date', '>=', date_from + ' 00:00:00'))
            if date_to: ik_dom.append(('create_date', '<=', date_to + ' 23:59:59'))
            records = self.env['donation.in.kind'].search(ik_dom)
            agg = {}
            for rec in records:
                if not rec.donor_id: continue
                total_amt = sum([(line.quantity * line.avg_price) for line in rec.donation_in_kind_line_ids])
                if rec.donor_id.id not in agg:
                    agg[rec.donor_id.id] = {'name': rec.donor_id.name, 'amount': 0.0, 'count': 0}
                agg[rec.donor_id.id]['amount'] += total_amt
                agg[rec.donor_id.id]['count'] += 1
            in_kind_top_donors = sorted(agg.values(), key=lambda x: x['amount'], reverse=True)[:10]

        return {
            'kpi': {
                'registered': registered, 'draft': draft, 'rejected': rejected,
                'donors': donors, 'donees': donees, 'individuals': individuals,
            },
            'chart_regs': {'labels': list(regs_by_month.keys()), 'data': list(regs_by_month.values())},
            'chart_cats': {'labels': list(cat_dist.keys()), 'data': list(cat_dist.values())},
            'recent_registrations': recent_registrations,
            'recent_drafts': recent_drafts,
            'pos_top_donors': pos_top_donors,
            'box_top_donors': box_top_donors,
            'home_top_donors': home_top_donors,
            'import_top_donors': import_top_donors,
            'online_top_donors': online_top_donors,
            'in_kind_top_donors': in_kind_top_donors,
        }