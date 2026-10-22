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

    def _date_sql(self, date_from, date_to, default_monthly=False,
                  default_yearly=False, table='pos_order'):
        """SQL fragment (leading AND) that filters `table`.date_order."""
        date_from = self._validate_date(date_from)
        date_to = self._validate_date(date_to)
        if date_from and date_to:
            return " AND %s.date_order::date BETWEEN '%s' AND '%s'" % (table, date_from, date_to)
        elif date_from:
            return " AND %s.date_order::date >= '%s'" % (table, date_from)
        elif date_to:
            return " AND %s.date_order::date <= '%s'" % (table, date_to)
        elif default_monthly:
            return " AND EXTRACT(month FROM %s.date_order::date) = EXTRACT(month FROM CURRENT_DATE)" % table
        elif default_yearly:
            return " AND EXTRACT(year FROM %s.date_order::date) = EXTRACT(year FROM CURRENT_DATE)" % table
        return ""

    def _date_domain(self, date_from, date_to):
        domain = []
        date_from = self._validate_date(date_from)
        date_to = self._validate_date(date_to)
        if date_from:
            domain.append(('date_order', '>=', date_from + ' 00:00:00'))
        if date_to:
            domain.append(('date_order', '<=', date_to + ' 23:59:59'))
        return domain

    def _date_filter_conditions(self, date_from, date_to, prefix='pos_order'):
        """For line-level queries that need to join pos_order."""
        conds = []
        date_from = self._validate_date(date_from)
        date_to = self._validate_date(date_to)
        if date_from:
            conds.append("%s.date_order::date >= '%s'" % (prefix, date_from))
        if date_to:
            conds.append("%s.date_order::date <= '%s'" % (prefix, date_to))
        return conds

    # ------------------------------------------------------------------
    # sales chart
    # ------------------------------------------------------------------
    @api.model
    def get_department(self, option, config_id=None, date_from=None, date_to=None):
        company_id = self.env.company.id
        shop_id = self._shop_id(config_id)
        shop_sql = (' AND pos_order.config_id = %d' % shop_id) if shop_id else ''

        default_monthly = option in ('pos_hourly_sales', 'pos_monthly_sales')
        default_yearly  = option == 'pos_year_sales'
        date_sql = self._date_sql(date_from, date_to,
                                  default_monthly=default_monthly,
                                  default_yearly=default_yearly)

        if option == 'pos_hourly_sales':
            user_tz = self.env.user.tz if self.env.user.tz else pytz.UTC
            query = (
                "select EXTRACT(hour FROM date_order at time zone 'utc' at time zone '%s') "
                "as date_month, sum(amount_total) from pos_order "
                "where pos_order.company_id = %d%s%s "
                "group by date_month order by date_month"
            ) % (user_tz, company_id, shop_sql, date_sql)
            label = 'HOURS'
        elif option == 'pos_monthly_sales':
            query = (
                "select date_order::date as date_month, sum(amount_total) from pos_order "
                "where pos_order.company_id = %d%s%s "
                "group by date_month order by date_month"
            ) % (company_id, shop_sql, date_sql)
            label = 'DAYS'
        else:
            query = (
                "select TO_CHAR(date_order,'MON') as date_month, sum(amount_total) from pos_order "
                "where pos_order.company_id = %d%s%s "
                "group by date_month, EXTRACT(month FROM date_order) "
                "order by EXTRACT(month FROM date_order)"
            ) % (company_id, shop_sql, date_sql)
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
    def get_details(self, config_id=None, date_from=None, date_to=None):
        company_id = self.env.company.id
        shop_id = self._shop_id(config_id)
        shop_sql = (' AND pos_order.config_id = %d' % shop_id) if shop_id else ''
        date_sql = self._date_sql(date_from, date_to)
        cr = self._cr

        # ---------- payment methods ----------
        cr.execute("""
            select pos_payment_method.name->>'en_US', sum(amount)
            from pos_payment
            inner join pos_payment_method on pos_payment_method.id = pos_payment.payment_method_id
            inner join pos_order on pos_order.id = pos_payment.pos_order_id
            where pos_order.company_id = %d%s%s
            group by pos_payment_method.name
            order by sum(amount) DESC
        """ % (company_id, shop_sql, date_sql))
        payment_details = cr.fetchall()

        # ---------- salesperson ----------
        cr.execute("""
            select hr_employee.name, sum(pos_order.amount_paid) as total,
                   count(pos_order.amount_paid) as orders
            from pos_order
            inner join hr_employee on pos_order.user_id = hr_employee.user_id
            where pos_order.company_id = %d%s%s
            group by hr_employee.name
            order by total DESC
        """ % (company_id, shop_sql, date_sql))
        salesperson = cr.fetchall()

        # ---------- sessions ----------
        configs = self.env['pos.config'].search([('id', '=', shop_id)] if shop_id else [])
        states_label = {'opened': 'Opened', 'opening_control': 'Opening Control'}
        sessions_list = [
            {'session': c.name, 'status': states_label.get(c.pos_session_state, 'Closed')}
            for c in configs
        ]

        # ---------- currency formatting ----------
        currency = self.env.company.currency_id
        def _fmt(v):
            return ("%s %s" % (v, currency.symbol) if currency.position == 'after'
                    else "%s %s" % (currency.symbol, v))

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
    def get_refund_details(self, config_id=None, date_from=None, date_to=None):
        shop_id = self._shop_id(config_id)
        domain = []
        if shop_id:
            domain.append(('config_id', '=', shop_id))
        domain.extend(self._date_domain(date_from, date_to))
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

        if shop_id:
            total_session = 1 if self.env['pos.config'].search_count([('id', '=', shop_id)]) else 0
        else:
            total_session = self.env['pos.session'].search_count([])

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
    def get_the_top_customer(self, config_id=None, date_from=None, date_to=None):
        company_id = self.env.company.id
        shop_id = self._shop_id(config_id)
        shop_sql = (' AND pos_order.config_id = %d' % shop_id) if shop_id else ''
        date_sql = self._date_sql(date_from, date_to)
        self._cr.execute("""
            select res_partner.name as customer, pos_order.partner_id,
                   sum(pos_order.amount_paid) as amount_total
            from pos_order
            inner join res_partner on res_partner.id = pos_order.partner_id
            where pos_order.company_id = %d%s%s
            group by pos_order.partner_id, res_partner.name
            order by amount_total DESC
            limit 10
        """ % (company_id, shop_sql, date_sql))
        docs = self._cr.dictfetchall()
        return [[r.get('amount_total') for r in docs], [r.get('customer') for r in docs]]

    @api.model
    def get_the_top_products(self, config_id=None, date_from=None, date_to=None):
        company_id = self.env.company.id
        shop_id = self._shop_id(config_id)

        conds = []
        if shop_id:
            conds.append('pos_order.config_id = %d' % shop_id)
        conds.extend(self._date_filter_conditions(date_from, date_to))

        if conds:
            join = ' inner join pos_order on pos_order.id = pos_order_line.order_id '
            where_extra = ' AND ' + ' AND '.join(conds)
        else:
            join = ''
            where_extra = ''

        self._cr.execute("""
            select (product_template.name)->>'en_US' as product_name,
                   sum(case when qty > 0 then qty else 0 end) as sales_qty,
                   sum(case when qty < 0 then qty else 0 end) as refund_qty
            from pos_order_line
            inner join product_product on product_product.id = pos_order_line.product_id
            inner join product_template on product_product.product_tmpl_id = product_template.id
            %s
            where pos_order_line.company_id = %d%s
            group by product_template.id
            order by ABS(sum(qty)) DESC
            limit 10
        """ % (join, company_id, where_extra))
        docs = self._cr.dictfetchall()
        
        # Return 3 arrays: [Sales Data, Refund Data, Labels]
        return [
            [r.get('sales_qty') for r in docs],
            [r.get('refund_qty') for r in docs],
            [r.get('product_name') for r in docs]
        ]

    @api.model
    def get_the_top_categories(self, config_id=None, date_from=None, date_to=None):
        company_id = self.env.company.id
        shop_id = self._shop_id(config_id)

        conds = []
        if shop_id:
            conds.append('pos_order.config_id = %d' % shop_id)
        conds.extend(self._date_filter_conditions(date_from, date_to))

        if conds:
            join = ' inner join pos_order on pos_order.id = pos_order_line.order_id '
            where_extra = ' AND ' + ' AND '.join(conds)
        else:
            join = ''
            where_extra = ''

        self._cr.execute("""
            select product_category.complete_name as product_category,
                   sum(case when qty > 0 then qty else 0 end) as sales_qty,
                   sum(case when qty < 0 then qty else 0 end) as refund_qty
            from pos_order_line
            inner join product_product on product_product.id = pos_order_line.product_id
            inner join product_template on product_product.product_tmpl_id = product_template.id
            inner join product_category on product_category.id = product_template.categ_id
            %s
            where pos_order_line.company_id = %d%s
            group by product_category
            order by ABS(sum(qty)) DESC
            limit 10
        """ % (join, company_id, where_extra))
        docs = self._cr.dictfetchall()
        
        # Return 3 arrays: [Sales Data, Refund Data, Labels]
        return [
            [r.get('sales_qty') for r in docs],
            [r.get('refund_qty') for r in docs],
            [r.get('product_category') for r in docs]
        ]