# -*- coding: utf-8 -*-
import pytz
from datetime import datetime
from odoo import api, models


class PosOrder(models.Model):
    """Inherited pos.order to add dashboard data."""
    _inherit = 'pos.order'

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @api.model
    def get_shops(self):
        """List of POS configurations ('shops') for the dropdown."""
        configs = self.env['pos.config'].search([])
        return [{'id': c.id, 'name': c.name} for c in configs]

    def _shop_id(self, config_id):
        try:
            return int(config_id) if config_id else None
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # sales chart
    # ------------------------------------------------------------------
    @api.model
    def get_department(self, option, config_id=None):
        company_id = self.env.company.id
        shop_id = self._shop_id(config_id)
        shop = (' AND pos_order.config_id = %d' % shop_id) if shop_id else ''

        if option == 'pos_hourly_sales':
            user_tz = self.env.user.tz if self.env.user.tz else pytz.UTC
            query = (
                "select EXTRACT(hour FROM date_order at time zone 'utc' at time zone '%s') "
                "as date_month, sum(amount_total) from pos_order where "
                "EXTRACT(month FROM date_order::date) = EXTRACT(month FROM CURRENT_DATE) "
                "AND pos_order.company_id = %d%s "
                "group by date_month "
            ) % (user_tz, company_id, shop)
            label = 'HOURS'
        elif option == 'pos_monthly_sales':
            query = (
                "select date_order::date as date_month, sum(amount_total) from pos_order where "
                "EXTRACT(month FROM date_order::date) = EXTRACT(month FROM CURRENT_DATE) "
                "AND pos_order.company_id = %d%s "
                "group by date_month "
            ) % (company_id, shop)
            label = 'DAYS'
        else:
            query = (
                "select TO_CHAR(date_order,'MON') date_month, sum(amount_total) from pos_order where "
                "EXTRACT(year FROM date_order::date) = EXTRACT(year FROM CURRENT_DATE) "
                "AND pos_order.company_id = %d%s "
                "group by date_month "
            ) % (company_id, shop)
            label = 'MONTHS'

        self._cr.execute(query)
        docs = self._cr.dictfetchall()
        order = [record.get('sum') for record in docs]
        today = [record.get('date_month') for record in docs]
        return [order, today, label]

    # ------------------------------------------------------------------
    # tile data + tables
    # ------------------------------------------------------------------
    @api.model
    def get_details(self, config_id=None):
        company_id = self.env.company.id
        shop_id = self._shop_id(config_id)
        cr = self._cr

        # ---------- payment details ----------
        if shop_id:
            cr.execute("""
                select pos_payment_method.name->>'en_US', sum(amount)
                from pos_payment
                inner join pos_payment_method on pos_payment_method.id = pos_payment.payment_method_id
                inner join pos_order on pos_order.id = pos_payment.pos_order_id
                where pos_order.config_id = %d
                group by pos_payment_method.name
                order by sum(amount) DESC;
            """ % shop_id)
        else:
            cr.execute("""
                select pos_payment_method.name->>'en_US', sum(amount)
                from pos_payment
                inner join pos_payment_method on pos_payment_method.id = pos_payment.payment_method_id
                group by pos_payment_method.name
                order by sum(amount) DESC;
            """)
        payment_details = cr.fetchall()

        # ---------- salesperson ----------
        shop = (' AND pos_order.config_id = %d' % shop_id) if shop_id else ''
        cr.execute("""
            select hr_employee.name, sum(pos_order.amount_paid) as total,
                   count(pos_order.amount_paid) as orders
            from pos_order
            inner join hr_employee on pos_order.user_id = hr_employee.user_id
            where pos_order.company_id = %d%s
            group by hr_employee.name
            order by total DESC;
        """ % (company_id, shop))
        salesperson = cr.fetchall()

        # ---------- top 10 products (kept from original, unused by view) ----------
        if shop_id:
            prod_join = ' inner join pos_order on pos_order.id = pos_order_line.order_id '
            prod_where = ' AND pos_order.config_id = %d' % shop_id
        else:
            prod_join = ''
            prod_where = ''
        cr.execute("""
            select DISTINCT(product_template.name) as product_name, sum(qty) as total_quantity
            from pos_order_line
            inner join product_product on product_product.id = pos_order_line.product_id
            inner join product_template on product_product.product_tmpl_id = product_template.id
            %s
            where pos_order_line.company_id = %d%s
            group by product_template.id
            order by total_quantity DESC
            limit 10
        """ % (prod_join, company_id, prod_where))
        cr.fetchall()  # unused by the view, but kept for parity

        # ---------- session status (uses pos.config's own session state) ----------
        if shop_id:
            configs = self.env['pos.config'].search([('id', '=', shop_id)])
        else:
            configs = self.env['pos.config'].search([])
        states_label = {'opened': 'Opened', 'opening_control': 'Opening Control'}
        sessions_list = []
        for cfg in configs:
            st = states_label.get(cfg.pos_session_state)
            sessions_list.append({
                'session': cfg.name,
                'status': st or 'Closed',
            })

        # ---------- format currency once ----------
        currency = self.env.company.currency_id
        def _fmt(value):
            return ("%s %s" % (value, currency.symbol)
                    if currency.position == 'after'
                    else "%s %s" % (currency.symbol, value))

        payments = [(_fmt(r[1]), r[0]) for r in payment_details]
        # keep original tuple layout (name, amount) — swap to match template
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
    def get_refund_details(self, config_id=None):
        shop_id = self._shop_id(config_id)
        domain = [('config_id', '=', shop_id)] if shop_id else []
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
    def get_the_top_customer(self, config_id=None):
        company_id = self.env.company.id
        shop_id = self._shop_id(config_id)
        shop = (' AND pos_order.config_id = %d' % shop_id) if shop_id else ''
        self._cr.execute("""
            select res_partner.name as customer, pos_order.partner_id,
                   sum(pos_order.amount_paid) as amount_total
            from pos_order
            inner join res_partner on res_partner.id = pos_order.partner_id
            where pos_order.company_id = %d%s
            group by pos_order.partner_id, res_partner.name
            order by amount_total DESC
            limit 10;
        """ % (company_id, shop))
        docs = self._cr.dictfetchall()
        return [[r.get('amount_total') for r in docs], [r.get('customer') for r in docs]]

    @api.model
    def get_the_top_products(self, config_id=None):
        company_id = self.env.company.id
        shop_id = self._shop_id(config_id)
        if shop_id:
            join = ' inner join pos_order on pos_order.id = pos_order_line.order_id '
            where = ' AND pos_order.config_id = %d' % shop_id
        else:
            join, where = '', ''
        self._cr.execute("""
            select DISTINCT(product_template.name)->>'en_US' as product_name,
                   sum(qty) as total_quantity
            from pos_order_line
            inner join product_product on product_product.id = pos_order_line.product_id
            inner join product_template on product_product.product_tmpl_id = product_template.id
            %s
            where pos_order_line.company_id = %d%s
            group by product_template.id
            order by total_quantity DESC
            limit 10
        """ % (join, company_id, where))
        docs = self._cr.dictfetchall()
        return [[r.get('total_quantity') for r in docs], [r.get('product_name') for r in docs]]

    @api.model
    def get_the_top_categories(self, config_id=None):
        company_id = self.env.company.id
        shop_id = self._shop_id(config_id)
        if shop_id:
            join = ' inner join pos_order on pos_order.id = pos_order_line.order_id '
            where = ' AND pos_order.config_id = %d' % shop_id
        else:
            join, where = '', ''
        self._cr.execute("""
            select DISTINCT(product_category.complete_name) as product_category,
                   sum(qty) as total_quantity
            from pos_order_line
            inner join product_product on product_product.id = pos_order_line.product_id
            inner join product_template on product_product.product_tmpl_id = product_template.id
            inner join product_category on product_category.id = product_template.categ_id
            %s
            where pos_order_line.company_id = %d%s
            group by product_category
            order by total_quantity DESC
        """ % (join, company_id, where))
        docs = self._cr.dictfetchall()
        return [[r.get('total_quantity') for r in docs], [r.get('product_category') for r in docs]]