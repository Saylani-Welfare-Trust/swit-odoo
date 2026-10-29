# -*- coding: utf-8 -*-
import pytz
import re
from datetime import datetime, timedelta
from odoo import api, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @api.model
    def get_shops(self):
        configs = self.env['pos.config'].search([])
        shops = []
        for c in configs:
            province_id = False
            city_id = False
            zone_id = False
            
            if 'analytic_account_id' in c._fields and c.analytic_account_id:
                p = c.analytic_account_id.parent_id
                if p:
                    zone_id = p.id
                    p2 = p.parent_id
                    if p2:
                        city_id = p2.id
                        p3 = p2.parent_id
                        if p3:
                            province_id = p3.id
            
            shops.append({
                'id': c.id, 
                'name': c.name,
                'province_id': province_id,
                'city_id': city_id,
                'zone_id': zone_id,
            })
        return shops

    @api.model
    def get_location_hierarchy(self):
        provinces = self.env['account.analytic.account'].search([('parent_id', '=', False), ('plan_id.name', '=', 'Location')])
        cities = self.env['account.analytic.account'].search([('parent_id', 'in', provinces.ids)])
        zones = self.env['account.analytic.account'].search([('parent_id', 'in', cities.ids)])
        
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

    def _shop_id(self, config_id):
        try:
            return int(config_id) if config_id else None
        except (ValueError, TypeError):
            return None

    def _validate_date(self, d):
        if not d:
            return None
        d = str(d).strip()
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', d):
            return None
        return d

    def _date_domain(self, date_from, date_to):
        domain = []
        date_from = self._validate_date(date_from)
        date_to = self._validate_date(date_to)
        if date_from:
            domain.append(('date_order', '>=', date_from + ' 00:00:00'))
        if date_to:
            domain.append(('date_order', '<=', date_to + ' 23:59:59'))
        return domain

    def _get_treasury_date_domain(self, model, date_from, date_to):
        domain = []
        if date_from or date_to:
            date_field = 'create_date'
            is_datetime = True
            for f in ['date', 'transfer_date', 'deposit_date', 'create_date']:
                if f in model._fields:
                    date_field = f
                    is_datetime = model._fields[date_field].type == 'datetime'
                    break
            if date_from:
                domain.append((date_field, '>=', date_from + ' 00:00:00' if is_datetime else date_from))
            if date_to:
                domain.append((date_field, '<=', date_to + ' 23:59:59' if is_datetime else date_to))
        return domain

    def _get_order_domain(self, config_id=None, date_from=None, date_to=None,
                          province_id=None, city_id=None, zone_id=None, segment_id=None, segment_type=None):
        domain = []
        if config_id:
            domain.append(('config_id', '=', int(config_id)))
        domain.extend(self._date_domain(date_from, date_to))

        if province_id or city_id or zone_id or segment_id or segment_type:
            analytic_domain = []
            if province_id:
                analytic_domain.append(('id', 'child_of', int(province_id)))
            if city_id:
                analytic_domain.append(('id', 'child_of', int(city_id)))
            if zone_id:
                analytic_domain.append(('id', 'child_of', int(zone_id)))
            if segment_id:
                analytic_domain.append(('id', 'child_of', int(segment_id)))
            if segment_type:
                analytic_domain.append(('name', 'ilike', f'%({segment_type})%'))

            accounts = self.env['account.analytic.account'].search(analytic_domain)
            if not accounts:
                domain.append(('id', '=', 0))
            else:
                analytic_filters = []
                if 'analytic_account_id' in self._fields:
                    analytic_filters.append(('analytic_account_id', 'in', accounts.ids))
                if 'session_id' in self._fields:
                    analytic_filters.append(('session_id.analytic_account_id', 'in', accounts.ids))
                if 'config_id' in self._fields:
                    analytic_filters.append(('config_id.analytic_account_id', 'in', accounts.ids))
                if 'user_id' in self._fields:
                    analytic_filters.append(('user_id.employee_id.analytic_account_id', 'in', accounts.ids))

                if 'analytic_account_id' in self.env['product.template']._fields:
                    analytic_filters.append(('lines.product_id.product_tmpl_id.analytic_account_id', 'in', accounts.ids))
                elif 'analytic_account_ids' in self.env['product.template']._fields:
                    analytic_filters.append(('lines.product_id.product_tmpl_id.analytic_account_ids', 'in', accounts.ids))

                if analytic_filters:
                    if len(analytic_filters) == 1:
                        domain.extend(analytic_filters)
                    else:
                        or_operators = ['|'] * (len(analytic_filters) - 1)
                        domain.extend(or_operators + analytic_filters)
                else:
                    domain.append(('id', '=', 0))
        return domain

    def _apply_dashboard_filters(self, domain, category_id=None, amount_min=None, amount_max=None):
        if category_id:
            domain.append(('lines.product_id.categ_id', 'child_of', int(category_id)))
        if amount_min is not None:
            domain.append(('amount_total', '>=', float(amount_min)))
        if amount_max is not None:
            domain.append(('amount_total', '<=', float(amount_max)))
        return domain

    def _get_order_ids_sql(self, domain):
        if not domain:
            return ""
        orders = self.env['pos.order'].search(domain)
        if not orders:
            return " AND 1=0 "
        return " AND pos_order.id IN (%s) " % ','.join(str(i) for i in orders.ids)

    # ------------------------------------------------------------------
    # sales chart
    # ------------------------------------------------------------------
    @api.model
    def get_department(self, option, config_id=None, date_from=None, date_to=None,
                       province_id=None, city_id=None, zone_id=None, segment_id=None,
                       segment_type=None, category_id=None, amount_min=None, amount_max=None,
                       *extra, **kwargs):
        company_id = self.env.company.id
        domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, zone_id, segment_id, segment_type)
        domain = self._apply_dashboard_filters(domain, category_id, amount_min, amount_max)
        order_sql = self._get_order_ids_sql(domain)

        if "1=0" in order_sql:
            return [[], [], 'HOURS']

        if option == 'pos_hourly_sales':
            user_tz = self.env.user.tz if self.env.user.tz else pytz.UTC
            query = (
                "select EXTRACT(hour FROM date_order at time zone 'utc' at time zone '%s') "
                "as date_month, sum(amount_total) from pos_order "
                "where pos_order.company_id = %d %s "
                "group by date_month order by date_month"
            ) % (user_tz, company_id, order_sql)
            label = 'HOURS'
        elif option == 'pos_monthly_sales':
            query = (
                "select date_order::date as date_month, sum(amount_total) from pos_order "
                "where pos_order.company_id = %d %s "
                "group by date_month order by date_month"
            ) % (company_id, order_sql)
            label = 'DAYS'
        else:
            query = (
                "select TO_CHAR(date_order,'MON') as date_month, sum(amount_total) from pos_order "
                "where pos_order.company_id = %d %s "
                "group by date_month, EXTRACT(month FROM date_order) "
                "order by EXTRACT(month FROM date_order)"
            ) % (company_id, order_sql)
            label = 'MONTHS'

        self._cr.execute(query)
        docs = self._cr.dictfetchall()
        return [
            [r.get('sum') for r in docs],
            [r.get('date_month') for r in docs],
            label,
        ]

    # ------------------------------------------------------------------
    # tiles + tables
    # ------------------------------------------------------------------
    @api.model
    def get_details(self, config_id=None, date_from=None, date_to=None,
                    province_id=None, city_id=None, zone_id=None, segment_id=None,
                    segment_type=None, category_id=None, amount_min=None, amount_max=None,
                    *extra, **kwargs):
        company_id = self.env.company.id
        domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, zone_id, segment_id, segment_type)
        domain = self._apply_dashboard_filters(domain, category_id, amount_min, amount_max)
        order_sql = self._get_order_ids_sql(domain)
        cr = self._cr

        if "1=0" in order_sql:
            return {'payment_details': [], 'salesperson': [], 'selling_product': []}

        cr.execute("""
            select pos_payment_method.name->>'en_US', sum(amount)
            from pos_payment
            inner join pos_payment_method on pos_payment_method.id = pos_payment.payment_method_id
            inner join pos_order on pos_order.id = pos_payment.pos_order_id
            where pos_order.company_id = %d %s
            group by pos_payment_method.name
            order by sum(amount) DESC
        """ % (company_id, order_sql))
        payment_details = cr.fetchall()

        cr.execute("""
            select hr_employee.name, sum(pos_order.amount_paid) as total,
                   count(pos_order.amount_paid) as orders
            from pos_order
            inner join hr_employee on pos_order.user_id = hr_employee.user_id
            where pos_order.company_id = %d %s
            group by hr_employee.name
            order by total DESC
        """ % (company_id, order_sql))
        salesperson = cr.fetchall()

        configs = self.env['pos.config'].search([('id', '=', config_id)] if config_id else [])
        states_label = {'opened': 'Opened', 'opening_control': 'Opening Control'}
        sessions_list = [
            {'session': c.name, 'status': states_label.get(c.pos_session_state, 'Closed')}
            for c in configs
        ]

        currency = self.env.company.currency_id

        def _fmt(v):
            try:
                val = "{:,.2f}".format(float(v or 0.0))
            except (ValueError, TypeError):
                val = "0.00"
            return ("%s %s" % (val, currency.symbol) if currency.position == 'after'
                    else "%s %s" % (currency.symbol, val))

        payments = [(r[0], _fmt(r[1])) for r in payment_details]
        total_sales = [(r[0], _fmt(r[1]), r[2]) for r in salesperson]

        return {
            'payment_details': payments,
            'salesperson': total_sales,
            'selling_product': sessions_list,
        }

    # ------------------------------------------------------------------
    # tiles
    # ------------------------------------------------------------------
    @api.model
    def get_refund_details(self, config_id=None, date_from=None, date_to=None,
                           province_id=None, city_id=None, zone_id=None, segment_id=None,
                           segment_type=None, category_id=None, amount_min=None, amount_max=None,
                           *extra, **kwargs):
        domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, zone_id, segment_id, segment_type)
        domain = self._apply_dashboard_filters(domain, category_id, amount_min, amount_max)
        pos_orders = self.env['pos.order'].search(domain)

        default_date = datetime.today().date()
        total = 0
        today_refund_total = 0
        total_order_count = 0
        total_refund_count = 0
        today_sale = 0

        for rec in pos_orders:
            total += rec.amount_total
            total_order_count += 1
            if rec.date_order.date() == default_date:
                today_sale += 1
            if rec.amount_total < 0.0:
                total_refund_count += 1
                if rec.date_order.date() == default_date:
                    today_refund_total += 1

        magnitude = 0
        mag_total = total
        while abs(mag_total) >= 1000:
            magnitude += 1
            mag_total /= 1000.0
        val = '%.2f%s' % (mag_total, ['', 'K', 'M', 'G', 'T', 'P'][magnitude])

        session_domain = []
        if config_id:
            session_domain.append(('config_id', '=', int(config_id)))
        if date_from:
            session_domain.append(('start_at', '>=', date_from + ' 00:00:00'))
        if date_to:
            session_domain.append(('start_at', '<=', date_to + ' 23:59:59'))
        total_session = self.env['pos.session'].search_count(session_domain)

        return {
            'total_sale': val,
            'total_order_count': total_order_count,
            'total_refund_count': total_refund_count,
            'total_session': total_session,
            'today_refund_total': today_refund_total,
            'today_sale': today_sale,
        }

    # ------------------------------------------------------------------
    # charts
    # ------------------------------------------------------------------
    @api.model
    def get_the_top_customer(self, config_id=None, date_from=None, date_to=None,
                             province_id=None, city_id=None, zone_id=None, segment_id=None,
                             segment_type=None, category_id=None, amount_min=None, amount_max=None,
                             *extra, **kwargs):
        company_id = self.env.company.id
        domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, zone_id, segment_id, segment_type)
        domain = self._apply_dashboard_filters(domain, category_id, amount_min, amount_max)
        order_sql = self._get_order_ids_sql(domain)

        if "1=0" in order_sql:
            return [[], []]

        self._cr.execute("""
            select res_partner.name as customer, pos_order.partner_id,
                   sum(pos_order.amount_paid) as amount_total
            from pos_order
            inner join res_partner on res_partner.id = pos_order.partner_id
            where pos_order.company_id = %d %s
            group by pos_order.partner_id, res_partner.name
            order by amount_total DESC
            limit 10
        """ % (company_id, order_sql))
        docs = self._cr.dictfetchall()
        return [[r.get('amount_total') for r in docs], [r.get('customer') for r in docs]]

    @api.model
    def get_the_top_products(self, config_id=None, date_from=None, date_to=None,
                             province_id=None, city_id=None, zone_id=None, segment_id=None,
                             segment_type=None, category_id=None, amount_min=None, amount_max=None,
                             *extra, **kwargs):
        company_id = self.env.company.id
        domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, zone_id, segment_id, segment_type)
        domain = self._apply_dashboard_filters(domain, category_id, amount_min, amount_max)
        order_sql = self._get_order_ids_sql(domain)

        if "1=0" in order_sql:
            return [[], [], []]

        self._cr.execute("""
            select (product_template.name)->>'en_US' as product_name,
                   sum(case when qty > 0 then qty else 0 end) as sales_qty,
                   sum(case when qty < 0 then qty else 0 end) as refund_qty
            from pos_order_line
            inner join pos_order on pos_order.id = pos_order_line.order_id
            inner join product_product on product_product.id = pos_order_line.product_id
            inner join product_template on product_product.product_tmpl_id = product_template.id
            where pos_order_line.company_id = %d %s
            group by product_template.id
            order by ABS(sum(qty)) DESC
            limit 10
        """ % (company_id, order_sql))
        docs = self._cr.dictfetchall()
        return [
            [r.get('sales_qty') or 0 for r in docs],
            [r.get('refund_qty') or 0 for r in docs],
            [r.get('product_name') for r in docs],
        ]

    @api.model
    def get_the_top_categories(self, config_id=None, date_from=None, date_to=None,
                               province_id=None, city_id=None, zone_id=None, segment_id=None,
                               segment_type=None, category_id=None, amount_min=None, amount_max=None,
                               *extra, **kwargs):
        company_id = self.env.company.id
        domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, zone_id, segment_id, segment_type)
        domain = self._apply_dashboard_filters(domain, category_id, amount_min, amount_max)
        order_sql = self._get_order_ids_sql(domain)

        if "1=0" in order_sql:
            return [[], [], []]

        self._cr.execute("""
            select product_category.complete_name as product_category,
                   sum(case when qty > 0 then qty else 0 end) as sales_qty,
                   sum(case when qty < 0 then qty else 0 end) as refund_qty
            from pos_order_line
            inner join pos_order on pos_order.id = pos_order_line.order_id
            inner join product_product on product_product.id = pos_order_line.product_id
            inner join product_template on product_product.product_tmpl_id = product_template.id
            inner join product_category on product_category.id = product_template.categ_id
            where pos_order_line.company_id = %d %s
            group by product_category
            order by ABS(sum(qty)) DESC
            limit 10
        """ % (company_id, order_sql))
        docs = self._cr.dictfetchall()
        return [
            [r.get('sales_qty') or 0 for r in docs],
            [r.get('refund_qty') or 0 for r in docs],
            [r.get('product_category') for r in docs],
        ]

    # ------------------------------------------------------------------
    # treasury
    # ------------------------------------------------------------------
    @api.model
    def get_treasury_stats(self, config_id=None, date_from=None, date_to=None,
                           province_id=None, city_id=None, zone_id=None, segment_id=None,
                           segment_type=None, category_id=None, amount_min=None, amount_max=None,
                           *extra, **kwargs):
        order_domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, zone_id, segment_id, segment_type)
        order_domain = self._apply_dashboard_filters(order_domain, category_id, amount_min, amount_max)
        cheque_count = self.search_count(order_domain + [('pos_cheque_id', '!=', False)])

        analytic_domain = []
        if province_id:
            analytic_domain.append(('id', 'child_of', int(province_id)))
        if city_id:
            analytic_domain.append(('id', 'child_of', int(city_id)))
        if zone_id:
            analytic_domain.append(('id', 'child_of', int(zone_id)))
        if segment_id:
            analytic_domain.append(('id', 'child_of', int(segment_id)))
        if segment_type:
            analytic_domain.append(('name', 'ilike', f'%({segment_type})%'))

        accounts = self.env['account.analytic.account'].search(analytic_domain) if analytic_domain else None
        analytic_filter = []
        if analytic_domain:
            if accounts:
                analytic_filter.append(('analytic_account_id', 'in', accounts.ids))
            else:
                analytic_filter.append(('id', '=', 0))

        DD = self.env['direct.deposit']
        dd_domain = self._get_treasury_date_domain(DD, date_from, date_to) + analytic_filter
        deposit_count = DD.search_count(dd_domain)

        JT = self.env['journal.transfer']
        jt_domain = self._get_treasury_date_domain(JT, date_from, date_to) + analytic_filter
        transfer_count = JT.search_count(jt_domain)

        return {
            'cheque_count': cheque_count,
            'deposit_count': deposit_count,
            'transfer_count': transfer_count,
        }

    @api.model
    def action_get_treasury_orders(self, ttype, config_id=None, date_from=None, date_to=None,
                                   province_id=None, city_id=None, zone_id=None, segment_id=None,
                                   segment_type=None, category_id=None, amount_min=None, amount_max=None,
                                   *extra, **kwargs):
        analytic_domain = []
        if province_id:
            analytic_domain.append(('id', 'child_of', int(province_id)))
        if city_id:
            analytic_domain.append(('id', 'child_of', int(city_id)))
        if zone_id:
            analytic_domain.append(('id', 'child_of', int(zone_id)))
        if segment_id:
            analytic_domain.append(('id', 'child_of', int(segment_id)))
        if segment_type:
            analytic_domain.append(('name', 'ilike', f'%({segment_type})%'))

        accounts = self.env['account.analytic.account'].search(analytic_domain) if analytic_domain else None
        analytic_filter = []
        if analytic_domain:
            if accounts:
                analytic_filter.append(('analytic_account_id', 'in', accounts.ids))
            else:
                analytic_filter.append(('id', '=', 0))

        if ttype == 'cheque':
            order_domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, zone_id, segment_id, segment_type)
            order_domain = self._apply_dashboard_filters(order_domain, category_id, amount_min, amount_max)
            domain = order_domain + [('pos_cheque_id', '!=', False)]
            return {
                'name': 'POS Orders with Cheques',
                'type': 'ir.actions.act_window',
                'res_model': 'pos.order',
                'view_mode': 'list,form',
                'domain': domain,
                'target': 'current',
            }
        elif ttype == 'deposit':
            DD = self.env['direct.deposit']
            domain = self._get_treasury_date_domain(DD, date_from, date_to) + analytic_filter
            return {
                'name': 'Direct Deposits',
                'type': 'ir.actions.act_window',
                'res_model': 'direct.deposit',
                'view_mode': 'list,form',
                'domain': domain,
                'target': 'current',
            }
        elif ttype == 'transfer':
            JT = self.env['journal.transfer']
            domain = self._get_treasury_date_domain(JT, date_from, date_to) + analytic_filter
            return {
                'name': 'Journal Transfers',
                'type': 'ir.actions.act_window',
                'res_model': 'journal.transfer',
                'view_mode': 'list,form',
                'domain': domain,
                'target': 'current',
            }
            
    @api.model
    def get_top_products_by_amount(self, config_id=None, date_from=None, date_to=None,
                                   province_id=None, city_id=None, zone_id=None, segment_id=None,
                                   segment_type=None, category_id=None, amount_min=None, amount_max=None,
                                   *extra, **kwargs):
        company_id = self.env.company.id
        domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, zone_id, segment_id, segment_type)
        domain = self._apply_dashboard_filters(domain, category_id, amount_min, amount_max)
        order_sql = self._get_order_ids_sql(domain)

        if "1=0" in order_sql:
            return []

        self._cr.execute("""
            select (product_template.name)->>'en_US' as product_name,
                   sum(pos_order_line.price_subtotal_incl) as total_amount
            from pos_order_line
            inner join pos_order on pos_order.id = pos_order_line.order_id
            inner join product_product on product_product.id = pos_order_line.product_id
            inner join product_template on product_product.product_tmpl_id = product_template.id
            where pos_order_line.company_id = %d %s
            group by product_template.id, product_template.name
            order by total_amount DESC
            limit 10
        """ % (company_id, order_sql))
        
        docs = self._cr.dictfetchall()
        currency = self.env.company.currency_id
        result = []
        
        for r in docs:
            amount_val = r.get('total_amount') or 0.0
            try:
                val = "{:,.2f}".format(float(amount_val))
            except (ValueError, TypeError):
                val = "0.00"
            formatted_amount = ("%s %s" % (val, currency.symbol) if currency.position == 'after' 
                                else "%s %s" % (currency.symbol, val))
            
            result.append({
                'name': r.get('product_name') or 'Unknown',
                'amount': formatted_amount
            })
        return result
    
    
    @api.model
    def get_pos_categories(self):
        # Find all product templates that are available in POS
        templates = self.env['product.template'].search([('available_in_pos', '=', True)])
        # Get the categories assigned to those templates
        categs = templates.mapped('categ_id')
        
        # Include parent categories so the hierarchy makes sense
        parent_categs = self.env['product.category']
        for c in categs:
            if c.parent_id:
                parent_categs |= c.parent_id
                
        all_categs = (categs | parent_categs).sorted('complete_name')
        
        return [{'id': c.id, 'name': c.complete_name} for c in all_categs]
  
    @api.model
    def get_products_by_category_group(self, config_id=None, date_from=None, date_to=None,
                                    province_id=None, city_id=None, zone_id=None,
                                    segment_id=None, segment_type=None,
                                    category_id=None, amount_min=None, amount_max=None,
                                    *extra, **kwargs):
        company_id = self.env.company.id
        domain = self._get_order_domain(config_id, date_from, date_to, province_id,
                                        city_id, zone_id, segment_id, segment_type)
        domain = self._apply_dashboard_filters(domain, category_id, amount_min, amount_max)
        order_sql = self._get_order_ids_sql(domain)

        if "1=0" in order_sql:
            return {'cities': [], 'groups': []}

        location_plans = self.env['account.analytic.plan'].search([('name', '=', 'Location')])
        plan_ids_sql = ",".join(map(str, location_plans.ids)) if location_plans else "0"

        # 1. Join Product's Analytic Account
        if 'analytic_account_id' in self.env['product.template']._fields:
            pt_acc_join = "LEFT JOIN account_analytic_account pt_acc ON pt_acc.id = product_template.analytic_account_id"
        elif 'analytic_account_ids' in self.env['product.template']._fields:
            pt_acc_join = """
                LEFT JOIN LATERAL (
                    SELECT acc.id, acc.name, acc.parent_id
                    FROM account_analytic_account acc
                    INNER JOIN product_template_account_analytic_account_rel rel
                        ON rel.account_analytic_account_id = acc.id
                    WHERE rel.product_template_id = product_template.id
                    LIMIT 1
                ) pt_acc ON true
            """
        else:
            pt_acc_join = ""

        name_field = self.env['account.analytic.account']._fields['name']
        
        def _name_col(alias):
            # Added TRIM to ensure exact matches when comparing valid cities
            if name_field.translate:
                return f"TRIM(({alias}.name)->>'en_US')"
            return f"TRIM({alias}.name)"

        # 2. Dynamically check the custom 'City' field on pos.config
        pos_city_field = None
        for fname, fobj in self.env['pos.config']._fields.items():
            if fname in ['city_id', 'pos_city_id', 'city', 'x_city'] or 'city' in fname.lower():
                if fobj.type in ('char', 'many2one'):
                    pos_city_field = fname
                    break
            if fobj.string and isinstance(fobj.string, str) and 'city' in fobj.string.lower():
                if fobj.type in ('char', 'many2one'):
                    pos_city_field = fname
                    break
        
        if pos_city_field:
            fobj = self.env['pos.config']._fields[pos_city_field]
            if fobj.type == 'char':
                pos_city_join = ""
                pos_city_name_expr = f"COALESCE(NULLIF(TRIM(SPLIT_PART(pos_config.{pos_city_field}, '/', 2)), ''), NULLIF(TRIM(SPLIT_PART(pos_config.{pos_city_field}, '/', 1)), ''))"
            elif fobj.type == 'many2one':
                comodel = fobj.comodel_name
                if comodel == 'account.analytic.account':
                    pos_city_join = f"LEFT JOIN account_analytic_account pos_city ON pos_city.id = pos_config.{pos_city_field}"
                    pos_city_name_expr = _name_col('pos_city')
                elif comodel == 'res.city':
                    pos_city_join = f"LEFT JOIN res_city pos_city ON pos_city.id = pos_config.{pos_city_field}"
                    pos_city_name_expr = "pos_city.name"
                else:
                    table_name = comodel.replace('.', '_')
                    pos_city_join = f"LEFT JOIN {table_name} pos_city ON pos_city.id = pos_config.{pos_city_field}"
                    pos_city_name_expr = "pos_city.name"
            else:
                pos_city_join = ""
                pos_city_name_expr = "NULL"
        else:
            pos_city_join = ""
            pos_city_name_expr = "NULL"

        # 3. Join Product's Analytic hierarchy to find City
        if pt_acc_join:
            pt_city_join = f"""
                LEFT JOIN LATERAL (
                    SELECT
                        CASE
                            WHEN c2.id IS NOT NULL AND c3.id IS NULL THEN {_name_col('c1')}
                            WHEN c3.id IS NOT NULL AND c4.id IS NULL THEN {_name_col('c2')}
                            WHEN c4.id IS NOT NULL THEN {_name_col('c3')}
                            WHEN c2.id IS NULL THEN {_name_col('c1')}
                        END AS name
                    FROM account_analytic_account c1
                    LEFT JOIN account_analytic_account c2 ON c2.id = c1.parent_id
                    LEFT JOIN account_analytic_account c3 ON c3.id = c2.parent_id
                    LEFT JOIN account_analytic_account c4 ON c4.id = c3.parent_id
                    WHERE c1.id = pt_acc.id
                      AND c1.plan_id IN ({plan_ids_sql})
                ) pt_city ON true
            """
        else:
            pt_city_join = "LEFT JOIN (SELECT NULL AS name) pt_city ON true"

        # 4. Join POS Config's Branch Analytic hierarchy (fallback)
        pos_fb_city_join = f"""
            LEFT JOIN LATERAL (
                SELECT
                    CASE
                        WHEN c2.id IS NOT NULL AND c3.id IS NULL THEN {_name_col('c1')}
                        WHEN c3.id IS NOT NULL AND c4.id IS NULL THEN {_name_col('c2')}
                        WHEN c4.id IS NOT NULL THEN {_name_col('c3')}
                        WHEN c2.id IS NULL THEN NULL
                    END AS name
                FROM account_analytic_account c1
                LEFT JOIN account_analytic_account c2 ON c2.id = c1.parent_id
                LEFT JOIN account_analytic_account c3 ON c3.id = c2.parent_id
                LEFT JOIN account_analytic_account c4 ON c4.id = c3.parent_id
                WHERE c1.id = pos_config.analytic_account_id
                  AND c1.plan_id IN ({plan_ids_sql})
            ) pos_fb_city ON true
        """

        city_name_expr = f"COALESCE(pt_city.name, {pos_city_name_expr}, pos_fb_city.name, 'No City')"

        # 5. Filtering Logic
        having_clause = ""
        if city_id:
            city_rec = self.env['account.analytic.account'].browse(int(city_id))
            c_name = (city_rec.name.get('en_US') if isinstance(city_rec.name, dict) else city_rec.name) or ''
            if c_name:
                safe_c_name = c_name.replace("'", "''").strip()
                having_clause = f"HAVING {city_name_expr} = '{safe_c_name}'"

        query = f"""
            SELECT
                pc.complete_name                              AS category_name,
                {city_name_expr}                              AS city_name,
                (product_template.name)->>'en_US'             AS product_name,
                product_template.id                           AS product_id,
                COALESCE(AVG(pos_order_line.price_unit), 0)   AS unit_price,
                COALESCE(SUM(pos_order_line.price_subtotal_incl), 0) AS total_amount
            FROM pos_order_line
            INNER JOIN pos_order          ON pos_order.id = pos_order_line.order_id
            LEFT  JOIN pos_config         ON pos_config.id = pos_order.config_id
            {pos_city_join}
            {pos_fb_city_join}
            INNER JOIN product_product    ON product_product.id = pos_order_line.product_id
            INNER JOIN product_template   ON product_product.product_tmpl_id = product_template.id
            INNER JOIN product_category   AS pc ON pc.id = product_template.categ_id
            {pt_acc_join}
            {pt_city_join}
            WHERE pos_order_line.company_id = {company_id} {order_sql}
            GROUP BY pc.complete_name, {city_name_expr},
                    product_template.id, product_template.name
            {having_clause}
            ORDER BY pc.complete_name, {city_name_expr} NULLS LAST,
                    total_amount DESC
        """

        self._cr.execute(query)
        docs = self._cr.dictfetchall()

        # --- NEW: Get Valid Cities based on active filters ---
        valid_cities = None
        if city_id:
            city_rec = self.env['account.analytic.account'].browse(int(city_id))
            c_name = (city_rec.name.get('en_US') if isinstance(city_rec.name, dict) else city_rec.name) or ''
            if c_name:
                valid_cities = {c_name.strip()}
        elif province_id:
            cities = self.env['account.analytic.account'].search([('parent_id', '=', int(province_id))])
            valid_cities = set()
            for c in cities:
                c_name = (c.name.get('en_US') if isinstance(c.name, dict) else c.name) or ''
                if c_name:
                    valid_cities.add(c_name.strip())

        currency = self.env.company.currency_id

        def _fmt(v):
            try:
                val = "{:,.2f}".format(float(v or 0.0))
            except (ValueError, TypeError):
                val = "0.00"
            return ("%s %s" % (val, currency.symbol) if currency.position == 'after'
                    else "%s %s" % (currency.symbol, val))

        # --- PIVOTING LOGIC ---
        all_cities = set()
        grouped_products = {}

        for r in docs:
            city = (r.get('city_name') or 'No City').strip()
            
            # Ignore "No City" and only add cities that fall within the selected province/city
            if city != 'No City':
                if valid_cities is None or city in valid_cities:
                    all_cities.add(city)
                
            grp = self._categorize_category(r.get('category_name'))
            prod_id = r.get('product_id')

            if prod_id not in grouped_products:
                grouped_products[prod_id] = {
                    'group_name': grp,
                    'product_name': r.get('product_name') or 'Unknown',
                    'unit_price': float(r.get('unit_price') or 0.0),
                    'total_amount': 0.0,
                    'city_amount': {}
                }

            amt = float(r.get('total_amount') or 0.0)
            
            # The total amount will still include the "No City" amounts
            grouped_products[prod_id]['total_amount'] += amt
            grouped_products[prod_id]['city_amount'][city] = grouped_products[prod_id]['city_amount'].get(city, 0.0) + amt

        sorted_cities = sorted(list(all_cities))
        
        group_order = ['Nafla', 'Wajiba', 'Non-Donation', 'PoS',
                    'Donation In Kind', 'Donation Box', 'Other']
        
        groups_dict = {g: [] for g in group_order}
        for prod_id, pdata in grouped_products.items():
            if pdata['group_name'] in groups_dict:
                groups_dict[pdata['group_name']].append(pdata)

        result_groups = []
        for group_name in group_order:
            prods = groups_dict[group_name]
            if not prods:
                continue
                
            prods.sort(key=lambda x: x['total_amount'], reverse=True)
            
            for p in prods:
                p['unit_price_fmt'] = _fmt(p['unit_price'])
                p['total_amount_fmt'] = _fmt(p['total_amount'])
                p['city_amount'] = {c: _fmt(a) for c, a in p['city_amount'].items()}

            result_groups.append({
                'group_name': group_name,
                'products': prods
            })

        return {
            'cities': sorted_cities,
            'groups': result_groups
        }


    def _categorize_category(self, complete_name):
        name = complete_name or ''
        if 'Saleable / Nafla' in name:
            return 'Nafla'
        if 'Saleable / Wajiba' in name:
            return 'Wajiba'
        if 'Saleable / Non-Donation' in name:
            return 'Non-Donation'
        if 'Saleable / PoS' in name:
            return 'PoS'
        if 'Donation In Kind' in name:
            return 'Donation In Kind'
        if 'Donation Box' in name:
            return 'Donation Box'
        return 'Other'
    
    @api.model
    def get_category_group_time_series(self, config_id=None, date_from=None, date_to=None,
                                       province_id=None, city_id=None, zone_id=None,
                                       segment_id=None, segment_type=None,
                                       category_id=None, amount_min=None, amount_max=None,
                                       *extra, **kwargs):
        company_id = self.env.company.id
        
        # Enforce 1 year default if no date filter is provided
        if not date_from and not date_to:
            today = datetime.today()
            date_from = (today - timedelta(days=365)).strftime('%Y-%m-%d')
            date_to = today.strftime('%Y-%m-%d')

        domain = self._get_order_domain(config_id, date_from, date_to, province_id,
                                        city_id, zone_id, segment_id, segment_type)
        domain = self._apply_dashboard_filters(domain, category_id, amount_min, amount_max)
        order_sql = self._get_order_ids_sql(domain)

        if "1=0" in order_sql:
            return {'columns': [], 'groups': [], 'grand_totals': {}, 'grand_total': ''}

        self._cr.execute(f"""
            SELECT
                DATE_TRUNC('month', pos_order.date_order) AS month_date,
                TO_CHAR(pos_order.date_order, 'MON YY') AS month_label,
                pc.complete_name AS category_name,
                SUM(pos_order_line.price_subtotal_incl) AS amount
            FROM pos_order_line
            INNER JOIN pos_order ON pos_order.id = pos_order_line.order_id
            INNER JOIN product_product ON product_product.id = pos_order_line.product_id
            INNER JOIN product_template ON product_product.product_tmpl_id = product_template.id
            INNER JOIN product_category AS pc ON pc.id = product_template.categ_id
            WHERE pos_order_line.company_id = {company_id} {order_sql}
            GROUP BY month_date, month_label, pc.complete_name
            ORDER BY month_date, pc.complete_name
        """)
        docs = self._cr.dictfetchall()

        columns_set = set()
        # tree: { group_name: { sub_category_name: { 'months': { label: amt }, 'total': 0 } } }
        tree = {}
        
        for r in docs:
            month_label = r.get('month_label')
            category_name = r.get('category_name') or ''
            amt = float(r.get('amount') or 0.0)
            
            if not month_label: continue
            columns_set.add((r.get('month_date'), month_label)) 
            
            group_name = self._categorize_category(category_name)
            # Extract the leaf category name (e.g. "Saleable / Nafla / Aqiqa" -> "Aqiqa")
            sub_category = category_name.split(' / ')[-1].strip()
            
            if group_name not in tree:
                tree[group_name] = {}
            if sub_category not in tree[group_name]:
                tree[group_name][sub_category] = {'months': {}, 'total': 0.0}
                
            tree[group_name][sub_category]['months'][month_label] = tree[group_name][sub_category]['months'].get(month_label, 0.0) + amt
            tree[group_name][sub_category]['total'] += amt

        # Sort columns chronologically
        sorted_columns = [c[1] for c in sorted(list(columns_set))]
        
        group_order = ['Nafla', 'Wajiba', 'Non-Donation', 'PoS', 'Donation In Kind', 'Donation Box', 'Other']
        
        # Clean number formatter without currency symbol to fit the layout neatly
        def _fmt(v):
            if not v:
                return "0"
            try:
                return "{:,.0f}".format(float(v))
            except (ValueError, TypeError):
                return "0"

        result_groups = []
        grand_totals = {'months': {}, 'total': 0.0}
        
        for group_name in group_order:
            if group_name not in tree:
                continue
            
            sub_rows = []
            group_months = {}
            group_total = 0.0
            
            for sub_name, data in tree[group_name].items():
                row_months = {}
                for col in sorted_columns:
                    amt = data['months'].get(col, 0.0)
                    row_months[col] = _fmt(amt)
                    group_months[col] = group_months.get(col, 0.0) + amt
                    grand_totals['months'][col] = grand_totals['months'].get(col, 0.0) + amt
                
                group_total += data['total']
                grand_totals['total'] += data['total']
                
                sub_rows.append({
                    'name': sub_name,
                    'months': row_months,
                    'total': _fmt(data['total'])
                })
            
            group_totals_fmt = {col: _fmt(group_months.get(col, 0.0)) for col in sorted_columns}
            
            result_groups.append({
                'group_name': group_name,
                'rows': sub_rows,
                'totals': group_totals_fmt,
                'total': _fmt(group_total)
            })

        grand_totals_fmt = {col: _fmt(grand_totals['months'].get(col, 0.0)) for col in sorted_columns}

        return {
            'columns': sorted_columns,
            'groups': result_groups,
            'grand_totals': grand_totals_fmt,
            'grand_total': _fmt(grand_totals['total'])
        }