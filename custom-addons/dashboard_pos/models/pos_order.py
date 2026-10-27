# -*- coding: utf-8 -*-
import pytz
import re
from datetime import datetime
from odoo import api, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @api.model
    def get_shops(self):
        configs = self.env['pos.config'].search([])
        return [{'id': c.id, 'name': c.name} for c in configs]

    @api.model
    def get_location_hierarchy(self):
        provinces = self.env['account.analytic.account'].search([('parent_id', '=', False), ('plan_id.name', '=', 'Location')])
        cities = self.env['account.analytic.account'].search([('parent_id', 'in', provinces.ids)])
        segments = self.env['account.analytic.account'].search([('plan_id.name', 'ilike', 'Segment')])
        
        return {
            'provinces': [{'id': p.id, 'name': p.name} for p in provinces],
            'cities': [{'id': c.id, 'name': c.name, 'province_id': c.parent_id.id} for c in cities],
            'segments': [{'id': s.id, 'name': s.display_name} for s in segments],
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

    def _get_order_domain(self, config_id=None, date_from=None, date_to=None, province_id=None, city_id=None, segment_id=None):
        domain = []
        if config_id:
            domain.append(('config_id', '=', int(config_id)))
        domain.extend(self._date_domain(date_from, date_to))

        if province_id or city_id or segment_id:
            analytic_domain = []
            if province_id:
                analytic_domain.append(('id', 'child_of', int(province_id)))
            if city_id:
                analytic_domain.append(('id', 'child_of', int(city_id)))
            if segment_id:
                analytic_domain.append(('id', 'child_of', int(segment_id)))

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

                # FIXED: Correct Odoo prefix syntax for OR conditions
                if analytic_filters:
                    if len(analytic_filters) == 1:
                        domain.extend(analytic_filters)
                    else:
                        or_operators = ['|'] * (len(analytic_filters) - 1)
                        domain.extend(or_operators + analytic_filters)
                else:
                    domain.append(('id', '=', 0))
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
    def get_department(self, option, config_id=None, date_from=None, date_to=None, province_id=None, city_id=None, segment_id=None):
        company_id = self.env.company.id
        domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, segment_id)
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
    def get_details(self, config_id=None, date_from=None, date_to=None, province_id=None, city_id=None, segment_id=None):
        company_id = self.env.company.id
        domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, segment_id)
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

        payments    = [(r[0], _fmt(r[1])) for r in payment_details]
        total_sales = [(r[0], _fmt(r[1]), r[2]) for r in salesperson]

        return {
            'payment_details': payments,
            'salesperson':     total_sales,
            'selling_product': sessions_list,
        }

    # ------------------------------------------------------------------
    # tiles
    # ------------------------------------------------------------------
    @api.model
    def get_refund_details(self, config_id=None, date_from=None, date_to=None, province_id=None, city_id=None, segment_id=None):
        domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, segment_id)
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
            'total_sale':         val,
            'total_order_count':  total_order_count,
            'total_refund_count': total_refund_count,
            'total_session':      total_session,
            'today_refund_total': today_refund_total,
            'today_sale':         today_sale,
        }

    # ------------------------------------------------------------------
    # charts
    # ------------------------------------------------------------------
    @api.model
    def get_the_top_customer(self, config_id=None, date_from=None, date_to=None, province_id=None, city_id=None, segment_id=None):
        company_id = self.env.company.id
        domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, segment_id)
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
    def get_the_top_products(self, config_id=None, date_from=None, date_to=None, province_id=None, city_id=None, segment_id=None):
        company_id = self.env.company.id
        domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, segment_id)
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
            [r.get('product_name') for r in docs]
        ]

    def _build_domain(self, config_id=None, date_from=None, date_to=None,
                    province_id=None, city_id=None, segment_id=None,
                    category_id=None, amount_min=None, amount_max=None):
        domain = []

        if config_id:
            domain.append(('config_id', '=', config_id))
        if date_from:
            domain.append(('date_order', '>=', date_from + ' 00:00:00'))
        if date_to:
            domain.append(('date_order', '<=', date_to + ' 23:59:59'))
        if province_id:
            domain.append(('config_id.x_province_id', '=', province_id))
        if city_id:
            domain.append(('config_id.x_city_id', '=', city_id))
        if segment_id:
            domain.append(('config_id.x_segment_id', '=', segment_id))

        # NEW: product category (match orders containing any line in this category tree)
        if category_id:
            domain.append(('lines.product_id.categ_id', 'child_of', category_id))

        # NEW: amount range
        if amount_min is not None:
            domain.append(('amount_total', '>=', amount_min))
        if amount_max is not None:
            domain.append(('amount_total', '<=', amount_max))

        return domain
    @api.model
    def get_the_top_categories(self, config_id=None, date_from=None, date_to=None, province_id=None, city_id=None, segment_id=None):
        company_id = self.env.company.id
        domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, segment_id)
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
            [r.get('product_category') for r in docs]
        ]

    # ------------------------------------------------------------------
    # treasury
    # ------------------------------------------------------------------
    @api.model
    def get_treasury_stats(self, config_id=None, date_from=None, date_to=None, province_id=None, city_id=None, segment_id=None):
        order_domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, segment_id)
        cheque_count = self.search_count(order_domain + [('pos_cheque_id', '!=', False)])

        analytic_domain = []
        if province_id: analytic_domain.append(('id', 'child_of', int(province_id)))
        if city_id: analytic_domain.append(('id', 'child_of', int(city_id)))
        if segment_id: analytic_domain.append(('id', 'child_of', int(segment_id)))
        
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
    def action_get_treasury_orders(self, ttype, config_id=None, date_from=None, date_to=None, province_id=None, city_id=None, segment_id=None):
        analytic_domain = []
        if province_id: analytic_domain.append(('id', 'child_of', int(province_id)))
        if city_id: analytic_domain.append(('id', 'child_of', int(city_id)))
        if segment_id: analytic_domain.append(('id', 'child_of', int(segment_id)))
        
        accounts = self.env['account.analytic.account'].search(analytic_domain) if analytic_domain else None
        analytic_filter = []
        if analytic_domain:
            if accounts:
                analytic_filter.append(('analytic_account_id', 'in', accounts.ids))
            else:
                analytic_filter.append(('id', '=', 0))

        if ttype == 'cheque':
            order_domain = self._get_order_domain(config_id, date_from, date_to, province_id, city_id, segment_id)
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