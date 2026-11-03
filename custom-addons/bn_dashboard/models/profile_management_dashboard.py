# -*- coding: utf-8 -*-
from odoo import api, models
import logging
import calendar
from datetime import date

_logger = logging.getLogger(__name__)

class ProfileManagementDashboard(models.TransientModel):
    _name = 'profile.management.dashboard'
    _description = 'Profile Management Dashboard'

    def _get_dashboard_data(self, date_from, date_to):
        domain = []
        if date_from: domain.append(('create_date', '>=', date_from + ' 00:00:00'))
        if date_to: domain.append(('create_date', '<=', date_to + ' 23:59:59'))

        Partner = self.env['res.partner']
        # --- NEW: Location Restriction ---
        # Note: You can only restrict models that have an analytic_account_id or similar link
        # For Partners, it might be difficult. For transactions (pos.order, welfare.line), it's easier.
        user = self.env.user
        if not user.has_group('base.group_system'):
            allowed_locs = user.get_allowed_analytic_ids()
            if not allowed_locs and (user.allowed_location_ids or user.allowed_warehouse_ids):
                allowed_locs = [0] # Force empty results if locations exist but don't map to analytic accounts
        else:
            allowed_locs = []
        
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

        # =========================================================================
        # HELPER: Dynamic Top 10 Aggregation (Scans fields automatically)
        # =========================================================================
        def get_top_orm(model_name, partner_fields, amount_fields, date_fields=['create_date', 'date', 'application_date'], custom_domain=None):
            if model_name not in self.env: return []
            Model = self.env[model_name]
            
            # Find Partner Field
            partner_field = next((f for f in partner_fields if f in Model._fields), None)
            if not partner_field:
                for f_name, f in Model._fields.items():
                    if f.type == 'many2one' and f.comodel_name == 'res.partner':
                        partner_field = f_name
                        break
            if not partner_field: return []
            
            # Find Amount Field
            amount_field = next((f for f in amount_fields if f in Model._fields), None)
            if not amount_field:
                for f_name, f in Model._fields.items():
                    if f.type in ['float', 'monetary'] and ('amount' in f_name or 'total' in f_name):
                        amount_field = f_name
                        break
                        
            # Find Date Field
            date_field = next((f for f in date_fields if f in Model._fields), None)
            
            # Build Domain
            dom = []
            if date_field:
                if date_from: dom.append((date_field, '>=', date_from + ' 00:00:00' if 'datetime' in Model._fields[date_field].type else date_from))
                if date_to: dom.append((date_field, '<=', date_to + ' 23:59:59' if 'datetime' in Model._fields[date_field].type else date_to))
            
            # --- ADD THIS BLOCK ---
            if custom_domain:
                dom.extend(custom_domain)
                
            # Try fast read_group first
            if amount_field:
                try:
                    groups = Model.read_group(dom, [partner_field, f'{amount_field}:sum'], [partner_field], limit=10, orderby=f'{amount_field} desc')
                    res = []
                    for g in groups:
                        if g[partner_field]:
                            val = g.get(amount_field) or g.get(f'{amount_field}:sum', 0.0)
                            res.append({'name': g[partner_field][1], 'amount': val, 'count': g.get('__count', 0)})
                    if res:
                        return res
                except Exception:
                    pass
            
            # Fallback to manual Python aggregation
            try:
                records = Model.search(dom, limit=5000)
                agg = {}
                for rec in records:
                    partner = getattr(rec, partner_field)
                    if not partner: continue
                    
                    val = 0.0
                    if amount_field:
                        try: val = float(getattr(rec, amount_field) or 0.0)
                        except: val = 0.0
                        
                    if partner.id not in agg:
                        agg[partner.id] = {'name': partner.name, 'amount': 0.0, 'count': 0}
                    agg[partner.id]['amount'] += val
                    agg[partner.id]['count'] += 1
                return sorted(agg.values(), key=lambda x: x['amount'], reverse=True)[:10]
            except Exception as e:
                _logger.error(f"Manual Top 10 Error {model_name}: {e}")
                return []

        # =========================================================================
        # DONORS TOP 10
        # =========================================================================
        pos_top_donors = get_top_orm('pos.order', ['partner_id'], ['amount_total'], ['date_order'])
        
        box_top_donors = []
        if 'rider.collection' in self.env:
            box_dom = [('state', 'in', ['donation_submit', 'pending', 'paid'])]
            if date_from: box_dom.append(('date', '>=', date_from))
            if date_to: box_dom.append(('date', '<=', date_to))
            collections = self.env['rider.collection'].search(box_dom)
            agg = {}
            for col in collections:
                if not col.donation_box_registration_installation_id or not col.donation_box_registration_installation_id.donor_id: continue
                donor = col.donation_box_registration_installation_id.donor_id
                if donor.id not in agg: agg[donor.id] = {'name': donor.name, 'amount': 0.0, 'count': 0}
                agg[donor.id]['amount'] += col.amount or 0.0
                agg[donor.id]['count'] += 1
            box_top_donors = sorted(agg.values(), key=lambda x: x['amount'], reverse=True)[:10]

        home_top_donors = []
        if 'donation.home.service' in self.env:
            hs_dom = []
            if date_from: hs_dom.append(('create_date', '>=', date_from + ' 00:00:00'))
            if date_to: hs_dom.append(('create_date', '<=', date_to + ' 23:59:59'))
            records = self.env['donation.home.service'].search(hs_dom)
            agg = {}
            for rec in records:
                if not rec.donor_id: continue
                amt = rec.total_amount or rec.amount or 0.0
                if rec.donor_id.id not in agg: agg[rec.donor_id.id] = {'name': rec.donor_id.name, 'amount': 0.0, 'count': 0}
                agg[rec.donor_id.id]['amount'] += amt
                agg[rec.donor_id.id]['count'] += 1
            home_top_donors = sorted(agg.values(), key=lambda x: x['amount'], reverse=True)[:10]

        import_top_donors = get_top_orm('donation', ['donor_id', 'partner_id'], ['amount', 'total_amount'])

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
                if rec.donor_id.id not in agg: agg[rec.donor_id.id] = {'name': rec.donor_id.name, 'amount': 0.0, 'count': 0}
                agg[rec.donor_id.id]['amount'] += amt
                agg[rec.donor_id.id]['count'] += 1
            online_top_donors = sorted(agg.values(), key=lambda x: x['amount'], reverse=True)[:10]

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
                if rec.donor_id.id not in agg: agg[rec.donor_id.id] = {'name': rec.donor_id.name, 'amount': 0.0, 'count': 0}
                agg[rec.donor_id.id]['amount'] += total_amt
                agg[rec.donor_id.id]['count'] += 1
            in_kind_top_donors = sorted(agg.values(), key=lambda x: x['amount'], reverse=True)[:10]

        # =========================================================================
        # DONEES TOP 10
        # =========================================================================
        
        # 1. Welfare (Manual aggregation from lines)
        welfare_top_donees = []
        if 'welfare.line' in self.env:
            wl_dom = []
            if date_from: wl_dom.append(('collection_date', '>=', date_from))
            if date_to: wl_dom.append(('collection_date', '<=', date_to))
            
            lines = self.env['welfare.line'].search(wl_dom)
            agg = {}
            for line in lines:
                if not line.welfare_id or not line.welfare_id.donee_id: continue
                donee = line.welfare_id.donee_id
                amt = line.total_amount or 0.0
                if donee.id not in agg:
                    agg[donee.id] = {'name': donee.name, 'amount': 0.0, 'count': 0}
                agg[donee.id]['amount'] += amt
                agg[donee.id]['count'] += 1
                
            if 'welfare.recurring.line' in self.env:
                wrl_dom = []
                if date_from: wrl_dom.append(('collection_date', '>=', date_from))
                if date_to: wrl_dom.append(('collection_date', '<=', date_to))
                rlines = self.env['welfare.recurring.line'].search(wrl_dom)
                for line in rlines:
                    if not line.welfare_id or not line.welfare_id.donee_id: continue
                    donee = line.welfare_id.donee_id
                    amt = line.amount or 0.0
                    if donee.id not in agg:
                        agg[donee.id] = {'name': donee.name, 'amount': 0.0, 'count': 0}
                    agg[donee.id]['amount'] += amt
                    agg[donee.id]['count'] += 1

            welfare_top_donees = sorted(agg.values(), key=lambda x: x['amount'], reverse=True)[:10]

        # 2. Microfinance (Dynamic Model Finder)
        microfinance_top_donees = []
        micro_models = ['microfinance.application', 'microfinance.loan', 'microfinance.request', 'microfinance']
        for m in micro_models:
            if m in self.env:
                microfinance_top_donees = get_top_orm(m, ['donee_id', 'partner_id'], ['total_amount', 'loan_amount', 'amount', 'requested_amount'])
                if microfinance_top_donees: break

        # 3. Medical (Dynamic Model Finder)
        medical_top_donees = []
        med_models = ['medical.equipment', 'medical.equipment.request', 'medical.equipment.issue']
        for m in med_models:
            if m in self.env:
                medical_top_donees = get_top_orm(m, ['donee_id', 'partner_id'], ['total_amount', 'amount'])
                if medical_top_donees: break

        return {
            'kpi': {
                'registered': registered, 'draft': draft, 'rejected': rejected,
                'donors': donors, 'donees': donees, 'individuals': individuals,
            },
            'chart_regs': {'labels': list(regs_by_month.keys()), 'data': list(regs_by_month.values())},
            'chart_cats': {'labels': list(cat_dist.keys()), 'data': list(cat_dist.values())},
            'pos_top_donors': pos_top_donors,
            'box_top_donors': box_top_donors,
            'home_top_donors': home_top_donors,
            'import_top_donors': import_top_donors,
            'online_top_donors': online_top_donors,
            'in_kind_top_donors': in_kind_top_donors,
            'welfare_top_donees': welfare_top_donees,
            'microfinance_top_donees': microfinance_top_donees,
            'medical_top_donees': medical_top_donees,
        }

    @api.model
    def get_comparison_data(self, mode='month', period1=None, period2=None):
        """Return KPI counts for two periods so the dashboard can compare them."""
        

        def _parse_period(period_str, mode):
            if not period_str:
                return None, None
            try:
                if mode == 'month':
                    year, month = map(int, str(period_str).split('-'))
                    start = date(year, month, 1)
                    end = date(year, month, calendar.monthrange(year, month)[1])
                else:
                    year = int(period_str)
                    start = date(year, 1, 1)
                    end = date(year, 12, 31)
            except (ValueError, TypeError):
                return None, None
            return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')

        p1_start, p1_end = _parse_period(period1, mode)
        p2_start, p2_end = _parse_period(period2, mode)

        empty = {
            'registered': 0, 'draft': 0, 'rejected': 0,
            'donors': 0, 'donees': 0, 'individuals': 0,
        }
        if not p1_start or not p2_start:
            return {'p1': empty, 'p2': empty, 'diffs': {}, 'mode': mode,
                    'period1': period1, 'period2': period2}

        Partner = self.env['res.partner']

        def _count_period(start, end):
            d = [
                ('create_date', '>=', start + ' 00:00:00'),
                ('create_date', '<=', end + ' 23:59:59'),
            ]
            return {
                'registered': Partner.search_count(d + [('state', '=', 'register')]),
                'draft': Partner.search_count(d + [('state', '=', 'draft')]),
                'rejected': Partner.search_count(d + [('state', '=', 'reject')]),
                'donors': Partner.search_count(d + [('category_id.name', 'ilike', 'Donor')]),
                'donees': Partner.search_count(d + [('category_id.name', 'ilike', 'Donee')]),
                'individuals': Partner.search_count(d + [('category_id.name', 'ilike', 'Individual')]),
            }

        p1 = _count_period(p1_start, p1_end)
        p2 = _count_period(p2_start, p2_end)

        diffs = {}
        for key in p1:
            v1 = p1[key]
            v2 = p2[key]
            diff = v2 - v1
            pct = 0.0
            if v1 > 0:
                pct = (diff / v1) * 100
            elif v2 > 0:
                pct = 100.0
            diffs[key] = {
                'diff': diff,
                'pct': pct,
                'is_positive': diff >= 0,
            }

        return {'p1': p1, 'p2': p2, 'diffs': diffs,
                'mode': mode, 'period1': period1, 'period2': period2}