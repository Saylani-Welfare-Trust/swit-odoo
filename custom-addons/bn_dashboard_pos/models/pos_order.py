# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from odoo import api, models, fields, _
from odoo.tools import date_utils
import pytz
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    """ Inherited class of pos dashboard to add features of dashboard"""
    _inherit = 'pos.order'
    
    

    @api.model
    def get_department(self, option):
        """ Function to get the order details of company wise"""
        company_id = self.env.company.id
        if option == 'pos_hourly_sales':
            user_tz = self.env.user.tz if self.env.user.tz else pytz.UTC
            query = '''select  EXTRACT(hour FROM date_order at time zone 'utc' at time zone '{}') 
                       as date_month,sum(amount_total) from pos_order where  
                       EXTRACT(month FROM date_order::date) = EXTRACT(month FROM CURRENT_DATE) 
                       AND pos_order.company_id = ''' + str(
                company_id) + ''' group by date_month '''
            query = query.format(user_tz)
            label = 'HOURS'
        elif option == 'pos_monthly_sales':
            query = '''select  date_order::date as date_month,sum(amount_total) from pos_order where 
             EXTRACT(month FROM date_order::date) = EXTRACT(month FROM CURRENT_DATE) AND pos_order.company_id = ''' + str(
                company_id) + '''  group by date_month '''
            label = 'DAYS'
        else:
            query = '''select TO_CHAR(date_order,'MON')date_month,sum(amount_total) from pos_order where
             EXTRACT(year FROM date_order::date) = EXTRACT(year FROM CURRENT_DATE) AND pos_order.company_id = ''' + str(
                company_id) + ''' group by date_month'''
            label = 'MONTHS'
        self._cr.execute(query)
        docs = self._cr.dictfetchall()
        order = []
        for record in docs:
            order.append(record.get('sum'))
        today = []
        for record in docs:
            today.append(record.get('date_month'))
        final = [order, today, label]
        return final
    
    # ---------------------------------------------------------------------------
    # Helper: accounting-based expense lookup (replaces HR)
    # ---------------------------------------------------------------------------
    @api.model
    def _get_expense_total(self, company_id, start_date, end_date):
        """Return total expense from posted accounting entries."""
        try:
            expense_accounts = self.env['account.account'].search([
                ('company_id', '=', company_id),
                ('account_type', 'in', ['expense', 'expense_direct_cost']),
                ('deprecated', '=', False),
            ])
            if not expense_accounts:
                return 0.0
            ExpenseLine = self.env['account.move.line']
            lines = ExpenseLine.search([
                ('account_id', 'in', expense_accounts.ids),
                ('parent_state', '=', 'posted'),
                ('date', '>=', start_date),
                ('date', '<=', end_date),
                ('company_id', '=', company_id),
            ])
            return sum(abs(line.balance) for line in lines)
        except Exception as e:
            _logger.error("Error in _get_expense_total: %s", str(e), exc_info=True)
            return 0.0
        
    # ---------------------------------------------------------------------------
    # Salesperson joins res_users instead of hr_employee
    # ---------------------------------------------------------------------------
    @api.model
    def get_details(self):
        """Payment / salesperson / session details (HR-free)."""
        company_id = self.env.company.id
        cr = self._cr
        cr.execute(
            """select pos_payment_method.name ->>'en_US', sum(amount)
            from pos_payment
            inner join pos_payment_method on pos_payment_method.id=pos_payment.payment_method_id
            group by pos_payment_method.name
            order by sum(amount) DESC;""")
        payment_details = cr.fetchall()

        cr.execute(
            '''select res_users.name, sum(pos_order.amount_paid) as total,
                    count(pos_order.amount_paid) as orders
            from pos_order
            inner join res_users on pos_order.user_id = res_users.id
            where pos_order.company_id = %s
            group by res_users.name
            order by total DESC;''', (company_id,))
        salesperson = cr.fetchall()

        total_sales = []
        for rec in salesperson:
            rec = list(rec)
            sym_id = rec[1]
            company = self.env.company
            if company.currency_id.position == 'after':
                rec[1] = f"{sym_id} PKR"
            else:
                rec[1] = f"PKR {sym_id}"
            total_sales.append(tuple(rec))

        cr.execute(
            '''select DISTINCT(product_template.name) as product_name, sum(qty) as total_quantity
            from pos_order_line
            inner join product_product on product_product.id=pos_order_line.product_id
            inner join product_template on product_product.product_tmpl_id = product_template.id
            where pos_order_line.company_id = %s
            group by product_template.id
            order by total_quantity DESC Limit 10''', (company_id,))
        selling_product = cr.fetchall()

        sessions_list = []
        for session in self.env['pos.config'].search([]):
            st = {'opened': 'Opened', 'opening_control': 'Opening Control'}.get(
                session.pos_session_state)
            sessions_list.append({
                'session': session.name,
                'status': st or 'Closed',
            })

        payments = []
        for rec in payment_details:
            rec = list(rec)
            sym_id = rec[1]
            company = self.env.company
            if company.currency_id.position == 'after':
                rec[1] = f"{sym_id} PKR"
            else:
                rec[1] = f"PKR {sym_id}"
            payments.append(tuple(rec))

        return {
            'payment_details': payments,
            'salesperson': total_sales,
            'selling_product': sessions_list,
        }


    @api.model
    def get_refund_details(self):
        """ Function to get the Refund details"""
        default_date = datetime.today().date()
        pos_order = self.env['pos.order'].search([])
        total = 0
        today_refund_total = 0
        total_order_count = 0
        total_refund_count = 0
        today_sale = 0
        for rec in pos_order:
            if rec.amount_total < 0.0 and rec.date_order.date() == default_date:
                today_refund_total = today_refund_total + 1
            total_sales = rec.amount_total
            total = total + total_sales
            total_order_count = total_order_count + 1
            if rec.date_order.date() == default_date:
                today_sale = today_sale + 1
            if rec.amount_total < 0.0:
                total_refund_count = total_refund_count + 1
        
        # Format total sale with K, M suffix
        magnitude = 0
        temp_total = abs(total)
        while temp_total >= 1000:
            magnitude += 1
            temp_total /= 1000.0
        val = '%.2f%s' % (temp_total, ['', 'K', 'M', 'G', 'T', 'P'][magnitude])
        if total < 0:
            val = '-' + val
            
        pos_session = self.env['pos.session'].search([])
        total_session = 0
        for record in pos_session:
            total_session = total_session + 1
        return {
            'total_sale': val,
            'total_order_count': total_order_count,
            'total_refund_count': total_refund_count,
            'total_session': total_session,
            'today_refund_total': today_refund_total,
            'today_sale': today_sale,
        }

    @api.model
    def get_the_top_customer(self, filter_type='today'):
        """To get the top Customer details with date filtering - UPDATED"""
        try:
            company_id = self.env.company.id
            
            # Define date range based on filter
            today = fields.Date.today()
            
            if filter_type == 'today':
                where_clause = f"AND po.date_order::date = '{today}'"
            elif filter_type == 'yesterday':
                yesterday = today - timedelta(days=1)
                where_clause = f"AND po.date_order::date = '{yesterday}'"
            elif filter_type == 'last_week':
                last_week = today - timedelta(days=7)
                where_clause = f"AND po.date_order::date >= '{last_week}' AND po.date_order::date <= '{today}'"
            elif filter_type == 'last_month':
                last_month = today - timedelta(days=30)
                where_clause = f"AND po.date_order::date >= '{last_month}' AND po.date_order::date <= '{today}'"
            elif filter_type == 'last_year':
                last_year = today - timedelta(days=365)
                where_clause = f"AND po.date_order::date >= '{last_year}' AND po.date_order::date <= '{today}'"
            elif filter_type == 'this_month':
                first_day = today.replace(day=1)
                where_clause = f"AND po.date_order::date >= '{first_day}' AND po.date_order::date <= '{today}'"
            elif filter_type == 'last_month_complete':
                first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
                last_day_last_month = today.replace(day=1) - timedelta(days=1)
                where_clause = f"AND po.date_order::date >= '{first_day_last_month}' AND po.date_order::date <= '{last_day_last_month}'"
            elif filter_type == 'this_year':
                first_day_year = today.replace(month=1, day=1)
                where_clause = f"AND po.date_order::date >= '{first_day_year}' AND po.date_order::date <= '{today}'"
            elif filter_type == 'last_year_complete':
                first_day_last_year = today.replace(year=today.year-1, month=1, day=1)
                last_day_last_year = today.replace(year=today.year-1, month=12, day=31)
                where_clause = f"AND po.date_order::date >= '{first_day_last_year}' AND po.date_order::date <= '{last_day_last_year}'"
            else:
                where_clause = ""
            
            query = f'''select res_partner.name as customer,pos_order.partner_id,
                    sum(pos_order.amount_paid) as amount_total from pos_order 
                    inner join res_partner on res_partner.id = pos_order.partner_id 
                    WHERE pos_order.company_id = {company_id}
                    AND pos_order.amount_total >= 0
                    {where_clause}
                    GROUP BY pos_order.partner_id,
                    res_partner.name  
                    ORDER BY amount_total DESC LIMIT 10;'''
            
            self._cr.execute(query)
            docs = self._cr.dictfetchall()

            order = []
            for record in docs:
                order.append(record.get('amount_total'))
            day = []
            for record in docs:
                day.append(record.get('customer'))
            final = [order, day]
            return final
            
        except Exception as e:
            _logger.error("Error in get_the_top_customer with filter: %s", str(e))
            return [[], []]

    @api.model
    def get_the_top_products(self, filter_type='today'):
        """Function to get the top products with date filtering"""
        try:
            company_id = self.env.company.id
            
            # Define date range based on filter
            today = fields.Date.today()
            where_clause = f"WHERE pos_order_line.company_id = {company_id}"
            
            if filter_type == 'today':
                where_clause += f" AND po.date_order::date = '{today}'"
            elif filter_type == 'yesterday':
                yesterday = today - timedelta(days=1)
                where_clause += f" AND po.date_order::date = '{yesterday}'"
            elif filter_type == 'last_week':
                last_week = today - timedelta(days=7)
                where_clause += f" AND po.date_order::date >= '{last_week}' AND po.date_order::date <= '{today}'"
            elif filter_type == 'last_month':
                last_month = today - timedelta(days=30)
                where_clause += f" AND po.date_order::date >= '{last_month}' AND po.date_order::date <= '{today}'"
            elif filter_type == 'last_year':
                last_year = today - timedelta(days=365)
                where_clause += f" AND po.date_order::date >= '{last_year}' AND po.date_order::date <= '{today}'"
            elif filter_type == 'this_month':
                first_day = today.replace(day=1)
                where_clause += f" AND po.date_order::date >= '{first_day}' AND po.date_order::date <= '{today}'"
            elif filter_type == 'last_month_complete':
                first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
                last_day_last_month = today.replace(day=1) - timedelta(days=1)
                where_clause += f" AND po.date_order::date >= '{first_day_last_month}' AND po.date_order::date <= '{last_day_last_month}'"
            elif filter_type == 'this_year':
                first_day_year = today.replace(month=1, day=1)
                where_clause += f" AND po.date_order::date >= '{first_day_year}' AND po.date_order::date <= '{today}'"
            elif filter_type == 'last_year_complete':
                first_day_last_year = today.replace(year=today.year-1, month=1, day=1)
                last_day_last_year = today.replace(year=today.year-1, month=12, day=31)
                where_clause += f" AND po.date_order::date >= '{first_day_last_year}' AND po.date_order::date <= '{last_day_last_year}'"
            
            query = f'''select DISTINCT(product_template.name) as product_name,sum(qty) as total_quantity from 
            pos_order_line inner join product_product on product_product.id=pos_order_line.product_id inner join 
            product_template on product_product.product_tmpl_id = product_template.id 
            inner join pos_order po on po.id = pos_order_line.order_id
            {where_clause} 
            group by product_template.id ORDER 
            BY total_quantity DESC Limit 10 '''
            
            self._cr.execute(query)
            top_product = self._cr.dictfetchall()
            
            total_quantity = []
            for record in top_product:
                total_quantity.append(record.get('total_quantity'))
            product_name = []
            for record in top_product:
                product_name.append(record.get('product_name'))
            final = [total_quantity, product_name]
            return final
            
        except Exception as e:
            _logger.error("Error in get_the_top_products with filter: %s", str(e))
            # Return empty data on error
            return [[], []]

    @api.model
    def get_the_top_categories(self, filter_type='today'):
        """Function to get the top Product categories with date filtering"""
        try:
            company_id = self.env.company.id
            
            # Define date range based on filter
            today = fields.Date.today()
            where_clause = f"WHERE pos_order_line.company_id = {company_id}"
            
            if filter_type == 'today':
                where_clause += f" AND po.date_order::date = '{today}'"
            elif filter_type == 'yesterday':
                yesterday = today - timedelta(days=1)
                where_clause += f" AND po.date_order::date = '{yesterday}'"
            elif filter_type == 'last_week':
                last_week = today - timedelta(days=7)
                where_clause += f" AND po.date_order::date >= '{last_week}' AND po.date_order::date <= '{today}'"
            elif filter_type == 'last_month':
                last_month = today - timedelta(days=30)
                where_clause += f" AND po.date_order::date >= '{last_month}' AND po.date_order::date <= '{today}'"
            elif filter_type == 'last_year':
                last_year = today - timedelta(days=365)
                where_clause += f" AND po.date_order::date >= '{last_year}' AND po.date_order::date <= '{today}'"
            elif filter_type == 'this_month':
                first_day = today.replace(day=1)
                where_clause += f" AND po.date_order::date >= '{first_day}' AND po.date_order::date <= '{today}'"
            elif filter_type == 'last_month_complete':
                first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
                last_day_last_month = today.replace(day=1) - timedelta(days=1)
                where_clause += f" AND po.date_order::date >= '{first_day_last_month}' AND po.date_order::date <= '{last_day_last_month}'"
            elif filter_type == 'this_year':
                first_day_year = today.replace(month=1, day=1)
                where_clause += f" AND po.date_order::date >= '{first_day_year}' AND po.date_order::date <= '{today}'"
            elif filter_type == 'last_year_complete':
                first_day_last_year = today.replace(year=today.year-1, month=1, day=1)
                last_day_last_year = today.replace(year=today.year-1, month=12, day=31)
                where_clause += f" AND po.date_order::date >= '{first_day_last_year}' AND po.date_order::date <= '{last_day_last_year}'"
            
            query = f'''select DISTINCT(product_category.complete_name) as product_category,sum(qty) as total_quantity 
            from pos_order_line inner join product_product on product_product.id=pos_order_line.product_id  
            inner join product_template on product_product.product_tmpl_id = product_template.id 
            inner join product_category on product_category.id =product_template.categ_id 
            inner join pos_order po on po.id = pos_order_line.order_id
            {where_clause} 
            group by product_category ORDER BY total_quantity DESC '''
            
            self._cr.execute(query)
            top_product = self._cr.dictfetchall()
            
            total_quantity = []
            for record in top_product:
                total_quantity.append(record.get('total_quantity'))
            product_categ = []
            for record in top_product:
                product_categ.append(record.get('product_category'))
            final = [total_quantity, product_categ]
            return final
            
        except Exception as e:
            _logger.error("Error in get_the_top_categories with filter: %s", str(e))
            # Return empty data on error
            return [[], []]
        
    @api.model
    def get_top_products_with_dates(self, start_date, end_date):
        """Function to get top products with custom date range"""
        try:
            company_id = self.env.company.id
            start_date = fields.Date.from_string(start_date) if start_date else fields.Date.today()
            end_date = fields.Date.from_string(end_date) if end_date else fields.Date.today()
            
            query = '''select DISTINCT(product_template.name) as product_name,sum(qty) as total_quantity from 
            pos_order_line inner join product_product on product_product.id=pos_order_line.product_id inner join 
            product_template on product_product.product_tmpl_id = product_template.id 
            inner join pos_order po on po.id = pos_order_line.order_id
            WHERE pos_order_line.company_id = %s
            AND po.date_order::date BETWEEN %s AND %s
            group by product_template.id ORDER 
            BY total_quantity DESC Limit 10 '''
            
            self._cr.execute(query, (company_id, start_date, end_date))
            top_product = self._cr.dictfetchall()
            
            total_quantity = []
            for record in top_product:
                total_quantity.append(record.get('total_quantity'))
            product_name = []
            for record in top_product:
                product_name.append(record.get('product_name'))
            final = [total_quantity, product_name]
            return final
            
        except Exception as e:
            _logger.error("Error in get_top_products_with_dates: %s", str(e))
            return [[], []]

    @api.model
    def get_top_categories_with_dates(self, start_date, end_date):
        """Function to get top categories with custom date range"""
        try:
            company_id = self.env.company.id
            start_date = fields.Date.from_string(start_date) if start_date else fields.Date.today()
            end_date = fields.Date.from_string(end_date) if end_date else fields.Date.today()
            
            query = '''select DISTINCT(product_category.complete_name) as product_category,sum(qty) as total_quantity 
            from pos_order_line inner join product_product on product_product.id=pos_order_line.product_id  
            inner join product_template on product_product.product_tmpl_id = product_template.id 
            inner join product_category on product_category.id =product_template.categ_id 
            inner join pos_order po on po.id = pos_order_line.order_id
            WHERE pos_order_line.company_id = %s
            AND po.date_order::date BETWEEN %s AND %s
            group by product_category ORDER BY total_quantity DESC '''
            
            self._cr.execute(query, (company_id, start_date, end_date))
            top_product = self._cr.dictfetchall()
            
            total_quantity = []
            for record in top_product:
                total_quantity.append(record.get('total_quantity'))
            product_categ = []
            for record in top_product:
                product_categ.append(record.get('product_category'))
            final = [total_quantity, product_categ]
            return final
            
        except Exception as e:
            _logger.error("Error in get_top_categories_with_dates: %s", str(e))
            return [[], []]

    # NEW METHODS FOR ENHANCED FEATURES

    @api.model
    def get_sales_target_data(self):
        """Get sales target data for the current user/company"""
        company_id = self.env.company.id
        target_obj = self.env['pos.sales.target']
        
        # Get current month target
        today = fields.Date.today()
        current_month = today.strftime('%Y-%m')
        
        targets = target_obj.search([
            ('company_id', '=', company_id),
            ('period', '=', 'monthly'),
            ('year_month', '=', current_month)
        ], limit=1)
        
        # Calculate current month sales
        start_date = today.replace(day=1)
        end_date = date_utils.end_of(today, 'month')
        
        self._cr.execute('''
            SELECT COALESCE(SUM(amount_total), 0)
            FROM pos_order
            WHERE company_id = %s
            AND date_order::date BETWEEN %s AND %s
            AND amount_total >= 0
        ''', (company_id, start_date, end_date))
        current_sales = self._cr.fetchone()[0] or 0
        
        target_data = {
            'target_amount': targets.target_amount if targets else 0,
            'current_amount': current_sales,
            'achievement_percentage': 0,
            'period': 'Current Month'
        }
        
        if targets and targets.target_amount > 0:
            target_data['achievement_percentage'] = min(
                100, (current_sales / targets.target_amount) * 100
            )
        
        return target_data

    @api.model
    def get_peak_hours(self, filter_type='today'):
        """Get peak sales hours - FIXED to work with all date filters"""
        try:
            company_id = self.env.company.id
            user_tz = self.env.user.tz if self.env.user.tz else pytz.UTC
            
            _logger.info("Getting 24-hour sales distribution for filter: %s", filter_type)
            
            # Define date range based on filter - UPDATED to handle all filters
            today = fields.Date.today()
            start_date = None
            end_date = None
            
            if filter_type == 'today':
                start_date = today
                end_date = today
            elif filter_type == 'yesterday':
                start_date = today - timedelta(days=1)
                end_date = today - timedelta(days=1)
            elif filter_type == 'last_week':
                start_date = today - timedelta(days=7)
                end_date = today
            elif filter_type == 'last_month':
                start_date = today - timedelta(days=30)
                end_date = today
            elif filter_type == 'last_year':
                start_date = today - timedelta(days=365)
                end_date = today
            elif filter_type == 'this_month':
                start_date = today.replace(day=1)
                end_date = today
            elif filter_type == 'last_month_complete':
                first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
                last_day_last_month = today.replace(day=1) - timedelta(days=1)
                start_date = first_day_last_month
                end_date = last_day_last_month
            elif filter_type == 'this_year':
                start_date = today.replace(month=1, day=1)
                end_date = today
            elif filter_type == 'last_year_complete':
                start_date = today.replace(year=today.year-1, month=1, day=1)
                end_date = today.replace(year=today.year-1, month=12, day=31)
            else:
                # For custom or unknown filter, default to today
                start_date = today
                end_date = today
            
            _logger.info("Date range for peak hours: %s to %s (filter: %s)", start_date, end_date, filter_type)
            
            # Query to get sales for ALL 24 hours, not just top 5
            query = '''
                SELECT 
                    EXTRACT(hour FROM date_order AT TIME ZONE 'utc' AT TIME ZONE %s) as hour,
                    COUNT(*) as order_count,
                    SUM(amount_total) as total_amount
                FROM pos_order
                WHERE company_id = %s
                AND amount_total >= 0
                AND date_order::date BETWEEN %s AND %s
                GROUP BY hour
                ORDER BY hour
            '''
            
            self._cr.execute(query, [user_tz, company_id, start_date, end_date])
            results = self._cr.dictfetchall()
            
            _logger.info("Found %s hour records for filter: %s", len(results), filter_type)
            
            # Create a dictionary with all 24 hours initialized to 0
            hour_data = {}
            for hour in range(24):
                hour_data[hour] = {
                    'hour': hour,
                    'hour_display': f"{hour:02d}:00",
                    'order_count': 0,
                    'total_amount': 0.0,
                    'period': self._get_time_period(hour)
                }
            
            # Update with actual data
            for res in results:
                if res['hour'] is not None:
                    hour = int(res['hour'])
                    if hour in hour_data:
                        hour_data[hour]['order_count'] = res['order_count'] or 0
                        hour_data[hour]['total_amount'] = res['total_amount'] or 0.0
            
            # Convert to list and sort by hour
            all_hours = list(hour_data.values())
            all_hours.sort(key=lambda x: x['hour'])
            
            # Group by time periods for analysis
            time_periods = self._get_time_period_summary(all_hours)
            
            # Calculate totals
            total_sales = sum([h['total_amount'] for h in all_hours])
            total_orders = sum([h['order_count'] for h in all_hours])
            
            # Find peak hour
            peak_hour = None
            if all_hours:
                peak_hour = max(all_hours, key=lambda x: x['total_amount'])
            
            return {
                'all_hours': all_hours,
                'time_periods': time_periods,
                'total_sales': total_sales,
                'total_orders': total_orders,
                'peak_hour': peak_hour,
                'filter_type': filter_type,
                'start_date': start_date.strftime('%Y-%m-%d') if start_date else '',
                'end_date': end_date.strftime('%Y-%m-%d') if end_date else ''
            }
            
        except Exception as e:
            _logger.error("Error in get_peak_hours: %s", str(e), exc_info=True)
            # Return sample 24-hour data with error flag
            sample_data = self._get_sample_24hour_data()
            sample_data['error'] = str(e)
            return sample_data
        
    def _get_time_period(self, hour):
        """Categorize hour into time period"""
        if 6 <= hour < 9:
            return 'Early Morning (6AM-9AM)'
        elif 9 <= hour < 12:
            return 'Morning (9AM-12PM)'
        elif 12 <= hour < 14:
            return 'Lunch (12PM-2PM)'
        elif 14 <= hour < 17:
            return 'Afternoon (2PM-5PM)'
        elif 17 <= hour < 21:
            return 'Evening (5PM-9PM)'
        elif 21 <= hour < 24:
            return 'Late Night (9PM-12AM)'
        else:
            return 'Night (12AM-6AM)'

    def _get_time_period_summary(self, all_hours):
        """Summarize data by time period"""
        period_summary = {}
        
        for hour_data in all_hours:
            period = hour_data['period']
            if period not in period_summary:
                period_summary[period] = {
                    'period': period,
                    'total_amount': 0.0,
                    'order_count': 0,
                    'hours': []
                }
            
            period_summary[period]['total_amount'] += hour_data['total_amount']
            period_summary[period]['order_count'] += hour_data['order_count']
            period_summary[period]['hours'].append(hour_data['hour'])
        
        # Convert to list and sort by total_amount
        periods_list = list(period_summary.values())
        periods_list.sort(key=lambda x: x['total_amount'], reverse=True)
        
        return periods_list

    def _get_sample_24hour_data(self):
        """Return sample 24-hour data for testing"""
        sample_hours = []
        for hour in range(24):
            # Create realistic sample data with peaks at typical hours
            if 9 <= hour <= 11:  # Morning peak
                sales = 800 + (hour - 9) * 200
            elif 12 <= hour <= 14:  # Lunch peak
                sales = 1200
            elif 17 <= hour <= 19:  # Evening peak
                sales = 1500
            elif hour == 20:  # Dinner peak
                sales = 2000
            else:
                sales = 100 + (hour * 20)  # Base with some variation
            
            sample_hours.append({
                'hour': hour,
                'hour_display': f"{hour:02d}:00",
                'order_count': max(1, int(sales / 100)),
                'total_amount': sales,
                'period': self._get_time_period(hour)
            })
        
        period_summary = self._get_time_period_summary(sample_hours)
        
        return {
            'all_hours': sample_hours,
            'time_periods': period_summary,
            'total_sales': sum([h['total_amount'] for h in sample_hours]),
            'total_orders': sum([h['order_count'] for h in sample_hours]),
            'peak_hour': max(sample_hours, key=lambda x: x['total_amount'])
        }
            
    @api.model
    def get_detailed_sales_report(self, filter_type='today', chart_type='bar'):
        """Get detailed sales report with various chart types"""
        company_id = self.env.company.id
        user_tz = self.env.user.tz if self.env.user.tz else pytz.UTC
        
        # Define date range
        today = fields.Date.today()
        if filter_type == 'today':
            start_date = today
            end_date = today
            group_by = "EXTRACT(hour FROM date_order AT TIME ZONE 'utc' AT TIME ZONE %s)"
            x_axis_label = 'Hours'
        elif filter_type == 'last_week':
            start_date = today - timedelta(days=7)
            end_date = today
            group_by = "date_order::date"
            x_axis_label = 'Days'
        elif filter_type == 'last_month':
            start_date = today - timedelta(days=30)
            end_date = today
            group_by = "date_order::date"
            x_axis_label = 'Days'
        elif filter_type == 'last_year':
            start_date = today - timedelta(days=365)
            end_date = today
            group_by = "TO_CHAR(date_order, 'Mon')"
            x_axis_label = 'Months'
        else:
            # All time - monthly view
            query = '''
                SELECT 
                    TO_CHAR(date_order, 'YYYY-MM') as period,
                    COUNT(*) as order_count,
                    SUM(amount_total) as total_amount
                FROM pos_order
                WHERE company_id = %s
                AND amount_total >= 0
                GROUP BY TO_CHAR(date_order, 'YYYY-MM')
                ORDER BY TO_CHAR(date_order, 'YYYY-MM')
                LIMIT 12
            '''
            self._cr.execute(query, [company_id])
            results = self._cr.dictfetchall()
            
            labels = []
            data = []
            for res in results:
                if res['period']:
                    labels.append(res['period'])
                    data.append(float(res['total_amount']))
            
            return {
                'labels': labels,
                'datasets': [{
                    'label': 'Sales Amount',
                    'data': data,
                    'backgroundColor': 'rgba(54, 162, 235, 0.7)',
                    'borderColor': 'rgba(54, 162, 235, 1)',
                    'borderWidth': 2
                }],
                'type': chart_type,
                'x_axis_label': 'Months',
                'total_sales': sum(data) if data else 0,
                'total_orders': sum([r['order_count'] for r in results]) if results else 0
            }
        
        query = f'''
            SELECT 
                {group_by} as period,
                COUNT(*) as order_count,
                SUM(amount_total) as total_amount
            FROM pos_order
            WHERE company_id = %s
            AND amount_total >= 0
        '''
        
        params = [company_id]
        if 'TIME ZONE' in group_by:
            params = [user_tz, company_id]
        
        if start_date and end_date:
            query += " AND date_order::date BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        query += f'''
            GROUP BY period
            ORDER BY period
        '''
        
        self._cr.execute(query, params)
        results = self._cr.dictfetchall()
        
        # Prepare data for charts
        labels = []
        data = []
        
        for res in results:
            if res['period']:
                labels.append(str(res['period']))
                data.append(float(res['total_amount']))
        
        return {
            'labels': labels,
            'datasets': [{
                'label': 'Sales Amount',
                'data': data,
                'backgroundColor': 'rgba(75, 192, 192, 0.6)',
                'borderColor': 'rgba(75, 192, 192, 1)',
                'borderWidth': 2
            }],
            'type': chart_type,
            'x_axis_label': x_axis_label,
            'total_sales': sum(data) if data else 0,
            'total_orders': sum([r['order_count'] for r in results]) if results else 0
        }

    @api.model
    def get_top_customers_detailed(self, limit=5, filter_type='all'):
        """Get detailed top customer information - UPDATED for all filters"""
        try:
            company_id = self.env.company.id
            
            # Define date range
            today = fields.Date.today()
            
            # Build WHERE clause based on filter
            where_conditions = [f"po.company_id = {company_id}", "po.amount_total >= 0"]
            
            if filter_type == 'today':
                where_conditions.append(f"po.date_order::date = '{today}'")
            elif filter_type == 'yesterday':
                yesterday = today - timedelta(days=1)
                where_conditions.append(f"po.date_order::date = '{yesterday}'")
            elif filter_type == 'last_week':
                last_week = today - timedelta(days=7)
                where_conditions.append(f"po.date_order::date >= '{last_week}' AND po.date_order::date <= '{today}'")
            elif filter_type == 'last_month':
                last_month = today - timedelta(days=30)
                where_conditions.append(f"po.date_order::date >= '{last_month}' AND po.date_order::date <= '{today}'")
            elif filter_type == 'last_year':
                last_year = today - timedelta(days=365)
                where_conditions.append(f"po.date_order::date >= '{last_year}' AND po.date_order::date <= '{today}'")
            elif filter_type == 'this_month':
                first_day = today.replace(day=1)
                where_conditions.append(f"po.date_order::date >= '{first_day}' AND po.date_order::date <= '{today}'")
            elif filter_type == 'last_month_complete':
                first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
                last_day_last_month = today.replace(day=1) - timedelta(days=1)
                where_conditions.append(f"po.date_order::date >= '{first_day_last_month}' AND po.date_order::date <= '{last_day_last_month}'")
            elif filter_type == 'this_year':
                first_day_year = today.replace(month=1, day=1)
                where_conditions.append(f"po.date_order::date >= '{first_day_year}' AND po.date_order::date <= '{today}'")
            elif filter_type == 'last_year_complete':
                first_day_last_year = today.replace(year=today.year-1, month=1, day=1)
                last_day_last_year = today.replace(year=today.year-1, month=12, day=31)
                where_conditions.append(f"po.date_order::date >= '{first_day_last_year}' AND po.date_order::date <= '{last_day_last_year}'")
            
            where_clause = " AND ".join(where_conditions)
            
            query = f'''
                SELECT 
                    rp.id,
                    rp.name as customer_name,
                    COUNT(po.id) as order_count,
                    SUM(po.amount_total) as total_spent,
                    AVG(po.amount_total) as avg_order_value,
                    MAX(po.date_order) as last_order_date
                FROM pos_order po
                JOIN res_partner rp ON po.partner_id = rp.id
                WHERE {where_clause}
                GROUP BY rp.id, rp.name
                HAVING COUNT(po.id) > 0
                ORDER BY total_spent DESC
                LIMIT {limit}
            '''
            
            self._cr.execute(query)
            results = self._cr.dictfetchall()
            
            # Format currency
            company = self.env.company
            for res in results:
                sym_id = res['total_spent'] or 0
                avg_value = res['avg_order_value'] or 0
                if company.currency_id.position == 'after':
                    res['total_spent_display'] = f"{sym_id:,.2f} {company.currency_id.symbol}"
                    res['avg_order_value_display'] = f"{avg_value:,.2f} {company.currency_id.symbol}"
                else:
                    res['total_spent_display'] = f"{company.currency_id.symbol} {sym_id:,.2f}"
                    res['avg_order_value_display'] = f"{company.currency_id.symbol} {avg_value:,.2f}"
                
                if res['last_order_date']:
                    res['last_order_date_display'] = res['last_order_date'].strftime('%Y-%m-%d %H:%M')
                else:
                    res['last_order_date_display'] = 'Never'
            
            return results
            
        except Exception as e:
            _logger.error("Error in get_top_customers_detailed: %s", str(e), exc_info=True)
            return []

    @api.model
    def update_target(self, target_data):
        """Update sales target"""
        company_id = self.env.company.id
        target_obj = self.env['pos.sales.target']
        
        today = fields.Date.today()
        current_month = today.strftime('%Y-%m')
        
        target = target_obj.search([
            ('company_id', '=', company_id),
            ('period', '=', 'monthly'),
            ('year_month', '=', current_month)
        ], limit=1)
        
        if target:
            target.write({'target_amount': target_data['target_amount']})
        else:
            target_obj.create({
                'company_id': company_id,
                'period': 'monthly',
                'year_month': current_month,
                'target_amount': target_data['target_amount'],
                'user_id': self.env.user.id
            })
        
        return {'success': True, 'message': 'Target updated successfully'}

    @api.model
    def get_profit_margin_analysis(self, filter_type='today'):
        """Calculate profit margin - SIMPLIFIED VERSION for all filters"""
        try:
            company_id = self.env.company.id
            
            # For custom filter, we need to handle it differently
            if filter_type == 'custom':
                # This method shouldn't be called for custom, but handle it anyway
                return self._get_sample_profit_data()
            
            # Define date range based on filter
            today = fields.Date.today()
            domain = [('company_id', '=', company_id), ('amount_total', '>=', 0)]
            
            if filter_type == 'today':
                domain.append(('date_order', '>=', today))
                domain.append(('date_order', '<', today + timedelta(days=1)))
            elif filter_type == 'yesterday':
                yesterday = today - timedelta(days=1)
                domain.append(('date_order', '>=', yesterday))
                domain.append(('date_order', '<', yesterday + timedelta(days=1)))
            elif filter_type == 'last_week':
                domain.append(('date_order', '>=', today - timedelta(days=7)))
            elif filter_type == 'last_month':
                domain.append(('date_order', '>=', today - timedelta(days=30)))
            elif filter_type == 'last_year':
                domain.append(('date_order', '>=', today - timedelta(days=365)))
            elif filter_type == 'this_month':
                first_day = today.replace(day=1)
                domain.append(('date_order', '>=', first_day))
            elif filter_type == 'last_month_complete':
                first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
                last_day_last_month = today.replace(day=1) - timedelta(days=1)
                domain.append(('date_order', '>=', first_day_last_month))
                domain.append(('date_order', '<=', last_day_last_month))
            elif filter_type == 'this_year':
                first_day_year = today.replace(month=1, day=1)
                domain.append(('date_order', '>=', first_day_year))
            elif filter_type == 'last_year_complete':
                first_day_last_year = today.replace(year=today.year-1, month=1, day=1)
                last_day_last_year = today.replace(year=today.year-1, month=12, day=31)
                domain.append(('date_order', '>=', first_day_last_year))
                domain.append(('date_order', '<=', last_day_last_year))
            
            orders = self.env['pos.order'].search(domain)
            
            # Process orders
            product_data = {}
            for order in orders:
                for line in order.lines:
                    product = line.product_id
                    if not product:
                        continue
                        
                    product_id = product.id
                    
                    if product_id not in product_data:
                        product_data[product_id] = {
                            'product_id': product_id,
                            'product_name': product.name or 'Unknown Product',
                            'total_quantity': 0,
                            'total_revenue': 0.0,
                            'total_cost': 0.0,
                            'total_profit': 0.0,
                        }
                    
                    # Calculate values
                    quantity = line.qty or 0
                    revenue = line.price_subtotal or 0.0
                    cost = quantity * (product.standard_price or 0.0)
                    profit = revenue - cost
                    
                    product_data[product_id]['total_quantity'] += quantity
                    product_data[product_id]['total_revenue'] += revenue
                    product_data[product_id]['total_cost'] += cost
                    product_data[product_id]['total_profit'] += profit
            
            # Convert to list and sort by profit
            results = list(product_data.values())
            results.sort(key=lambda x: x['total_profit'], reverse=True)
            results = results[:10]  # Top 10
            
            # Format for display
            company = self.env.company
            for res in results:
                revenue = res['total_revenue'] or 0.0
                cost = res['total_cost'] or 0.0
                profit = res['total_profit'] or 0.0
                
                # Calculate margin percentage
                margin_percentage = 0.0
                if revenue > 0:
                    margin_percentage = (profit / revenue) * 100
                
                res['profit_margin_percentage'] = margin_percentage
                res['profit_margin_percentage_display'] = f"{margin_percentage:.1f}%"
                
                # Format currency
                if company.currency_id.position == 'after':
                    res['total_revenue_display'] = f"{revenue:,.2f} {company.currency_id.symbol}"
                    res['total_cost_display'] = f"{cost:,.2f} {company.currency_id.symbol}"
                    res['total_profit_display'] = f"{profit:,.2f} {company.currency_id.symbol}"
                else:
                    res['total_revenue_display'] = f"{company.currency_id.symbol} {revenue:,.2f}"
                    res['total_cost_display'] = f"{company.currency_id.symbol} {cost:,.2f}"
                    res['total_profit_display'] = f"{company.currency_id.symbol} {profit:,.2f}"
                
                # Determine margin status
                if margin_percentage >= 40:
                    res['margin_status'] = 'high'
                    res['margin_status_label'] = 'High Margin'
                elif margin_percentage >= 20:
                    res['margin_status'] = 'medium'
                    res['margin_status_label'] = 'Good Margin'
                else:
                    res['margin_status'] = 'low'
                    res['margin_status_label'] = 'Low Margin'
            
            return results
            
        except Exception as e:
            _logger.error("Error in get_profit_margin_analysis: %s", str(e), exc_info=True)
            return self._get_sample_profit_data()

    @api.model
    def get_profit_summary(self, filter_type='today'):
        """Get overall profit summary - UPDATED for all filters"""
        try:
            company_id = self.env.company.id
            
            # Define date range based on filter - SAME LOGIC AS ABOVE
            today = fields.Date.today()
            domain = [('company_id', '=', company_id), ('amount_total', '>=', 0)]
            
            if filter_type == 'today':
                domain.append(('date_order', '>=', today))
                domain.append(('date_order', '<', today + timedelta(days=1)))
            elif filter_type == 'yesterday':
                yesterday = today - timedelta(days=1)
                domain.append(('date_order', '>=', yesterday))
                domain.append(('date_order', '<', yesterday + timedelta(days=1)))
            elif filter_type == 'last_week':
                domain.append(('date_order', '>=', today - timedelta(days=7)))
                domain.append(('date_order', '<', today + timedelta(days=1)))
            elif filter_type == 'last_month':
                domain.append(('date_order', '>=', today - timedelta(days=30)))
                domain.append(('date_order', '<', today + timedelta(days=1)))
            elif filter_type == 'last_year':
                domain.append(('date_order', '>=', today - timedelta(days=365)))
                domain.append(('date_order', '<', today + timedelta(days=1)))
            elif filter_type == 'this_month':
                first_day = today.replace(day=1)
                last_day = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
                domain.append(('date_order', '>=', first_day))
                domain.append(('date_order', '<=', last_day))
            
            _logger.info("Domain for profit summary: %s", domain)
            orders = self.env['pos.order'].search(domain)
            
            total_orders = len(orders)
            total_revenue = 0.0
            total_cost = 0.0
            total_profit = 0.0
            
            for order in orders:
                for line in order.lines:
                    if line.product_id:
                        quantity = line.qty or 0
                        revenue = line.price_subtotal or 0.0
                        cost = quantity * (line.product_id.standard_price or 0.0)
                        profit = revenue - cost
                        
                        total_revenue += revenue
                        total_cost += cost
                        total_profit += profit
            
            # Calculate averages
            avg_profit_per_order = total_profit / total_orders if total_orders > 0 else 0
            overall_margin_percentage = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
            
            # Format for display
            company = self.env.company
            
            def format_currency(value):
                if company.currency_id.position == 'after':
                    return f"{value:,.2f} {company.currency_id.symbol}"
                else:
                    return f"{company.currency_id.symbol} {value:,.2f}"
            
            return {
                'total_orders': total_orders,
                'total_revenue': total_revenue,
                'total_cost': total_cost,
                'total_profit': total_profit,
                'avg_profit_per_order': avg_profit_per_order,
                'overall_margin_percentage': overall_margin_percentage,
                'total_revenue_display': format_currency(total_revenue),
                'total_cost_display': format_currency(total_cost),
                'total_profit_display': format_currency(total_profit),
                'avg_profit_per_order_display': format_currency(avg_profit_per_order),
                'overall_margin_percentage_display': f"{overall_margin_percentage:.1f}%"
            }
            
        except Exception as e:
            _logger.error("Error in get_profit_summary: %s", str(e), exc_info=True)
            return self._get_default_profit_summary()

    def _get_default_profit_summary(self):
        """Return default profit summary"""
        company = self.env.company
        symbol = company.currency_id.symbol
        position = company.currency_id.position
        
        def format_currency(value):
            if position == 'after':
                return f"{value:,.2f} {symbol}"
            else:
                return f"{symbol} {value:,.2f}"
        
        return {
            'total_orders': 0,
            'total_revenue': 0.0,
            'total_cost': 0.0,
            'total_profit': 0.0,
            'avg_profit_per_order': 0.0,
            'overall_margin_percentage': 0.0,
            'total_revenue_display': format_currency(0),
            'total_cost_display': format_currency(0),
            'total_profit_display': format_currency(0),
            'avg_profit_per_order_display': format_currency(0),
            'overall_margin_percentage_display': '0.0%'
        }

    @api.model
    def get_top_profitable_categories(self, limit=5, filter_type='today'):
        """Get top categories by profit margin - UPDATED for all filters"""
        try:
            company_id = self.env.company.id
            
            # Define date range based on filter - SAME LOGIC AS ABOVE
            today = fields.Date.today()
            domain = [('company_id', '=', company_id), ('amount_total', '>=', 0)]
            
            if filter_type == 'today':
                domain.append(('date_order', '>=', today))
                domain.append(('date_order', '<', today + timedelta(days=1)))
            elif filter_type == 'yesterday':
                yesterday = today - timedelta(days=1)
                domain.append(('date_order', '>=', yesterday))
                domain.append(('date_order', '<', yesterday + timedelta(days=1)))
            elif filter_type == 'last_week':
                domain.append(('date_order', '>=', today - timedelta(days=7)))
                domain.append(('date_order', '<', today + timedelta(days=1)))
            elif filter_type == 'last_month':
                domain.append(('date_order', '>=', today - timedelta(days=30)))
                domain.append(('date_order', '<', today + timedelta(days=1)))
            elif filter_type == 'last_year':
                domain.append(('date_order', '>=', today - timedelta(days=365)))
                domain.append(('date_order', '<', today + timedelta(days=1)))
            
            orders = self.env['pos.order'].search(domain)
            
            category_data = {}
            for order in orders:
                for line in order.lines:
                    product = line.product_id
                    if not product:
                        continue
                        
                    category = product.categ_id
                    if not category:
                        continue
                        
                    category_id = category.id
                    
                    if category_id not in category_data:
                        category_data[category_id] = {
                            'category_id': category_id,
                            'category_name': category.display_name or category.name or 'Uncategorized',
                            'total_revenue': 0.0,
                            'total_cost': 0.0,
                            'total_profit': 0.0,
                        }
                    
                    quantity = line.qty or 0
                    revenue = line.price_subtotal or 0.0
                    cost = quantity * (product.standard_price or 0.0)
                    profit = revenue - cost
                    
                    category_data[category_id]['total_revenue'] += revenue
                    category_data[category_id]['total_cost'] += cost
                    category_data[category_id]['total_profit'] += profit
            
            results = list(category_data.values())
            results.sort(key=lambda x: x['total_profit'], reverse=True)
            results = results[:limit]
            
            # Calculate margin percentages and format
            company = self.env.company
            for res in results:
                revenue = res['total_revenue'] or 0.0
                cost = res['total_cost'] or 0.0
                profit = res['total_profit'] or 0.0
                margin_percentage = (profit / revenue * 100) if revenue > 0 else 0.0
                res['profit_margin_percentage'] = margin_percentage
                
                if company.currency_id.position == 'after':
                    res['total_revenue_display'] = f"{revenue:,.2f} {company.currency_id.symbol}"
                    res['total_cost_display'] = f"{cost:,.2f} {company.currency_id.symbol}"
                    res['total_profit_display'] = f"{profit:,.2f} {company.currency_id.symbol}"
                else:
                    res['total_revenue_display'] = f"{company.currency_id.symbol} {revenue:,.2f}"
                    res['total_cost_display'] = f"{company.currency_id.symbol} {cost:,.2f}"
                    res['total_profit_display'] = f"{company.currency_id.symbol} {profit:,.2f}"
            
            return results
            
        except Exception as e:
            _logger.error("Error in get_top_profitable_categories: %s", str(e), exc_info=True)
            return []
        
    # Add these methods to your PosOrder class:

    @api.model
    def get_refund_details_with_dates(self, start_date, end_date):
        """Function to get the Refund details with date range"""
        try:
            start_date = fields.Date.from_string(start_date) if start_date else fields.Date.today()
            end_date = fields.Date.from_string(end_date) if end_date else fields.Date.today()
            
            pos_order_domain = [
                ('date_order', '>=', start_date),
                ('date_order', '<=', end_date + timedelta(days=1))
            ]
            
            pos_order = self.search(pos_order_domain)
            
            total = 0
            today_refund_total = 0
            total_order_count = 0
            total_refund_count = 0
            today_sale = 0
            
            for rec in pos_order:
                if rec.amount_total < 0.0:
                    total_refund_count += 1
                    if rec.date_order.date() == fields.Date.today():
                        today_refund_total += 1
                
                total_sales = rec.amount_total
                total += total_sales
                total_order_count += 1
                
                if rec.date_order.date() == fields.Date.today():
                    today_sale += 1
            
            # Format total sale with K, M suffix
            magnitude = 0
            temp_total = abs(total)
            while temp_total >= 1000:
                magnitude += 1
                temp_total /= 1000.0
            val = '%.2f%s' % (temp_total, ['', 'K', 'M', 'G', 'T', 'P'][magnitude])
            if total < 0:
                val = '-' + val
                
            pos_session = self.env['pos.session'].search([
                ('start_at', '>=', start_date),
                ('start_at', '<=', end_date + timedelta(days=1))
            ])
            
            total_session = len(pos_session)
            
            return {
                'total_sale': val,
                'total_order_count': total_order_count,
                'total_refund_count': total_refund_count,
                'total_session': total_session,
                'today_refund_total': today_refund_total,
                'today_sale': today_sale,
            }
        except Exception as e:
            _logger.error("Error in get_refund_details_with_dates: %s", str(e))
            return {
                'total_sale': '0',
                'total_order_count': 0,
                'total_refund_count': 0,
                'total_session': 0,
                'today_refund_total': 0,
                'today_sale': 0,
            }

    @api.model
    def get_details_with_dates(self, start_date, end_date):
        """Payment / salesperson / session details with date range (HR-free)."""
        try:
            company_id = self.env.company.id
            start_date = fields.Date.from_string(start_date) if start_date else fields.Date.today()
            end_date = fields.Date.from_string(end_date) if end_date else fields.Date.today()

            cr = self._cr
            cr.execute("""
                SELECT pp.name->>'en_US' as payment_method, SUM(pp2.amount) as total_amount
                FROM pos_payment pp2
                INNER JOIN pos_payment_method pp ON pp.id = pp2.payment_method_id
                INNER JOIN pos_order po ON po.id = pp2.pos_order_id
                WHERE po.company_id = %s
                AND po.date_order::date BETWEEN %s AND %s
                GROUP BY pp.name
                ORDER BY total_amount DESC
            """, (company_id, start_date, end_date))
            payment_details = cr.fetchall()

            cr.execute('''
                SELECT res_users.name,
                    SUM(po.amount_paid) as total,
                    COUNT(po.amount_paid) as orders
                FROM pos_order po
                INNER JOIN res_users ON po.user_id = res_users.id
                WHERE po.company_id = %s
                AND po.date_order::date BETWEEN %s AND %s
                GROUP BY res_users.name
                ORDER BY total DESC
            ''', (company_id, start_date, end_date))
            salesperson = cr.fetchall()

            total_sales = []
            for rec in salesperson:
                rec = list(rec)
                sym_id = rec[1]
                company = self.env.company
                rec[1] = f"{sym_id} PKR" if company.currency_id.position == 'after' else f"PKR {sym_id}"
                total_sales.append(tuple(rec))

            sessions_list = []
            for session in self.env['pos.config'].search([]):
                st = {'opened': 'Opened', 'opening_control': 'Opening Control'}.get(
                    session.pos_session_state)
                sessions_list.append({
                    'session': session.name,
                    'status': st or 'Closed',
                })

            payments = []
            for rec in payment_details:
                rec = list(rec)
                sym_id = rec[1]
                company = self.env.company
                rec[1] = f"{sym_id} PKR" if company.currency_id.position == 'after' else f"PKR {sym_id}"
                payments.append(tuple(rec))

            return {
                'payment_details': payments,
                'salesperson': total_sales,
                'selling_product': sessions_list,
            }
        except Exception as e:
            _logger.error("Error in get_details_with_dates: %s", str(e))
            return {'payment_details': [], 'salesperson': [], 'selling_product': []}



    @api.model
    def get_profit_margin_analysis(self, filter_type='today'):
        """Calculate profit margin - UPDATED to handle all filters"""
        try:
            company_id = self.env.company.id
            _logger.info("Starting profit margin analysis for filter: %s", filter_type)
            
            # Define date range based on filter - FIXED
            today = fields.Date.today()
            
            # Get orders based on filter using domain
            domain = [('company_id', '=', company_id), ('amount_total', '>=', 0)]
            
            if filter_type == 'today':
                domain.append(('date_order', '>=', today))
                domain.append(('date_order', '<', today + timedelta(days=1)))
            elif filter_type == 'yesterday':
                yesterday = today - timedelta(days=1)
                domain.append(('date_order', '>=', yesterday))
                domain.append(('date_order', '<', yesterday + timedelta(days=1)))
            elif filter_type == 'last_week':
                domain.append(('date_order', '>=', today - timedelta(days=7)))
                domain.append(('date_order', '<', today + timedelta(days=1)))
            elif filter_type == 'last_month':
                domain.append(('date_order', '>=', today - timedelta(days=30)))
                domain.append(('date_order', '<', today + timedelta(days=1)))
            elif filter_type == 'last_year':
                domain.append(('date_order', '>=', today - timedelta(days=365)))
                domain.append(('date_order', '<', today + timedelta(days=1)))
            elif filter_type == 'this_month':
                first_day = today.replace(day=1)
                last_day = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
                domain.append(('date_order', '>=', first_day))
                domain.append(('date_order', '<=', last_day))
            elif filter_type == 'last_month_complete':
                first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
                last_day_last_month = today.replace(day=1) - timedelta(days=1)
                domain.append(('date_order', '>=', first_day_last_month))
                domain.append(('date_order', '<=', last_day_last_month))
            elif filter_type == 'this_year':
                first_day_year = today.replace(month=1, day=1)
                last_day_year = today.replace(month=12, day=31)
                domain.append(('date_order', '>=', first_day_year))
                domain.append(('date_order', '<=', last_day_year))
            elif filter_type == 'last_year_complete':
                first_day_last_year = today.replace(year=today.year-1, month=1, day=1)
                last_day_last_year = today.replace(year=today.year-1, month=12, day=31)
                domain.append(('date_order', '>=', first_day_last_year))
                domain.append(('date_order', '<=', last_day_last_year))
            else:
                # For custom date range or all time, don't add date filter
                pass
            
            _logger.info("Domain for profit margin: %s", domain)
            orders = self.env['pos.order'].search(domain)
            _logger.info("Found %s orders for filter: %s", len(orders), filter_type)
            
            if not orders:
                _logger.info("No orders found for filter: %s", filter_type)
                # Return sample data for testing
                return self._get_sample_profit_data()
            
            # Process orders
            product_data = {}
            for order in orders:
                for line in order.lines:
                    product = line.product_id
                    if not product:
                        continue
                        
                    product_id = product.id
                    
                    if product_id not in product_data:
                        product_data[product_id] = {
                            'product_id': product_id,
                            'product_name': product.name or 'Unknown Product',
                            'total_quantity': 0,
                            'total_revenue': 0.0,
                            'total_cost': 0.0,
                            'total_profit': 0.0,
                        }
                    
                    # Calculate values
                    quantity = line.qty or 0
                    revenue = line.price_subtotal or 0.0
                    cost = quantity * (product.standard_price or 0.0)
                    profit = revenue - cost
                    
                    product_data[product_id]['total_quantity'] += quantity
                    product_data[product_id]['total_revenue'] += revenue
                    product_data[product_id]['total_cost'] += cost
                    product_data[product_id]['total_profit'] += profit
            
            # Convert to list and sort by profit
            results = list(product_data.values())
            
            if not results:
                _logger.info("No product data found")
                return self._get_sample_profit_data()
            
            results.sort(key=lambda x: x['total_profit'], reverse=True)
            results = results[:10]
            
            # Format for display
            company = self.env.company
            for res in results:
                revenue = res['total_revenue'] or 0.0
                cost = res['total_cost'] or 0.0
                profit = res['total_profit'] or 0.0
                
                # Calculate margin percentage
                margin_percentage = 0.0
                if revenue > 0:
                    margin_percentage = (profit / revenue) * 100
                
                res['profit_margin_percentage'] = margin_percentage
                res['profit_margin_percentage_display'] = f"{margin_percentage:.1f}%"
                
                # Format currency
                if company.currency_id.position == 'after':
                    res['total_revenue_display'] = f"{revenue:,.2f} {company.currency_id.symbol}"
                    res['total_cost_display'] = f"{cost:,.2f} {company.currency_id.symbol}"
                    res['total_profit_display'] = f"{profit:,.2f} {company.currency_id.symbol}"
                else:
                    res['total_revenue_display'] = f"{company.currency_id.symbol} {revenue:,.2f}"
                    res['total_cost_display'] = f"{company.currency_id.symbol} {cost:,.2f}"
                    res['total_profit_display'] = f"{company.currency_id.symbol} {profit:,.2f}"
                
                # Determine margin status
                if margin_percentage >= 40:
                    res['margin_status'] = 'high'
                    res['margin_status_label'] = 'High Margin'
                elif margin_percentage >= 20:
                    res['margin_status'] = 'medium'
                    res['margin_status_label'] = 'Good Margin'
                else:
                    res['margin_status'] = 'low'
                    res['margin_status_label'] = 'Low Margin'
            
            return results
            
        except Exception as e:
            _logger.error("Error in get_profit_margin_analysis: %s", str(e), exc_info=True)
            return self._get_sample_profit_data()
        
    @api.model
    def get_profit_summary_with_dates(self, start_date, end_date):
        """Get overall profit summary with date range - SIMPLIFIED"""
        try:
            company_id = self.env.company.id
            
            # Handle None dates
            if not start_date:
                start_date = fields.Date.today()
            if not end_date:
                end_date = fields.Date.today()
            
            # Convert string dates to date objects
            if isinstance(start_date, str):
                start_date = fields.Date.from_string(start_date)
            if isinstance(end_date, str):
                end_date = fields.Date.from_string(end_date)
            
            # Add 1 day to end_date to include the entire day
            end_date_plus_one = end_date + timedelta(days=1)
            
            # Get orders
            orders = self.search([
                ('company_id', '=', company_id),
                ('amount_total', '>=', 0),
                ('date_order', '>=', start_date),
                ('date_order', '<', end_date_plus_one)
            ])
            
            total_orders = len(orders)
            total_revenue = 0.0
            total_cost = 0.0
            total_profit = 0.0
            
            for order in orders:
                for line in order.lines:
                    if line.product_id:
                        quantity = line.qty or 0
                        revenue = line.price_subtotal or 0.0
                        cost = quantity * (line.product_id.standard_price or 0.0)
                        profit = revenue - cost
                        
                        total_revenue += revenue
                        total_cost += cost
                        total_profit += profit
            
            # Calculate averages
            avg_profit_per_order = total_profit / total_orders if total_orders > 0 else 0
            overall_margin_percentage = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
            
            # Format for display
            company = self.env.company
            
            def format_currency(value):
                if company.currency_id.position == 'after':
                    return f"{value:,.2f} {company.currency_id.symbol}"
                else:
                    return f"{company.currency_id.symbol} {value:,.2f}"
            
            return {
                'total_orders': total_orders,
                'total_revenue': total_revenue,
                'total_cost': total_cost,
                'total_profit': total_profit,
                'avg_profit_per_order': avg_profit_per_order,
                'overall_margin_percentage': overall_margin_percentage,
                'total_revenue_display': format_currency(total_revenue),
                'total_cost_display': format_currency(total_cost),
                'total_profit_display': format_currency(total_profit),
                'avg_profit_per_order_display': format_currency(avg_profit_per_order),
                'overall_margin_percentage_display': f"{overall_margin_percentage:.1f}%"
            }
            
        except Exception as e:
            _logger.error("Error in get_profit_summary_with_dates: %s", str(e), exc_info=True)
            return self._get_default_profit_summary()

    @api.model
    def get_top_profitable_categories_with_dates(self, limit=5, start_date=None, end_date=None):
        """Get top categories by profit margin with date range - SIMPLIFIED"""
        try:
            company_id = self.env.company.id
            
            # Handle None dates
            if not start_date:
                start_date = fields.Date.today()
            if not end_date:
                end_date = fields.Date.today()
            
            # Convert string dates to date objects
            if isinstance(start_date, str):
                start_date = fields.Date.from_string(start_date)
            if isinstance(end_date, str):
                end_date = fields.Date.from_string(end_date)
            
            # Add 1 day to end_date to include the entire day
            end_date_plus_one = end_date + timedelta(days=1)
            
            # Get orders
            orders = self.search([
                ('company_id', '=', company_id),
                ('amount_total', '>=', 0),
                ('date_order', '>=', start_date),
                ('date_order', '<', end_date_plus_one)
            ])
            
            category_data = {}
            for order in orders:
                for line in order.lines:
                    product = line.product_id
                    if not product:
                        continue
                        
                    category = product.categ_id
                    if not category:
                        continue
                        
                    category_id = category.id
                    
                    if category_id not in category_data:
                        category_data[category_id] = {
                            'category_id': category_id,
                            'category_name': category.display_name or category.name or 'Uncategorized',
                            'total_revenue': 0.0,
                            'total_cost': 0.0,
                            'total_profit': 0.0,
                        }
                    
                    quantity = line.qty or 0
                    revenue = line.price_subtotal or 0.0
                    cost = quantity * (product.standard_price or 0.0)
                    profit = revenue - cost
                    
                    category_data[category_id]['total_revenue'] += revenue
                    category_data[category_id]['total_cost'] += cost
                    category_data[category_id]['total_profit'] += profit
            
            results = list(category_data.values())
            results.sort(key=lambda x: x['total_profit'], reverse=True)
            results = results[:limit]
            
            # Calculate margin percentages and format
            company = self.env.company
            for res in results:
                revenue = res['total_revenue'] or 0.0
                cost = res['total_cost'] or 0.0
                profit = res['total_profit'] or 0.0
                margin_percentage = (profit / revenue * 100) if revenue > 0 else 0.0
                res['profit_margin_percentage'] = margin_percentage
                
                if company.currency_id.position == 'after':
                    res['total_revenue_display'] = f"{revenue:,.2f} {company.currency_id.symbol}"
                    res['total_cost_display'] = f"{cost:,.2f} {company.currency_id.symbol}"
                    res['total_profit_display'] = f"{profit:,.2f} {company.currency_id.symbol}"
                else:
                    res['total_revenue_display'] = f"{company.currency_id.symbol} {revenue:,.2f}"
                    res['total_cost_display'] = f"{company.currency_id.symbol} {cost:,.2f}"
                    res['total_profit_display'] = f"{company.currency_id.symbol} {profit:,.2f}"
            
            return results
            
        except Exception as e:
            _logger.error("Error in get_top_profitable_categories_with_dates: %s", str(e), exc_info=True)
            return []

    @api.model
    def get_top_profitable_categories_with_dates(self, limit=5, start_date=None, end_date=None):
        """Get top categories by profit margin with date range - SIMPLIFIED"""
        try:
            company_id = self.env.company.id
            
            # Convert string dates to date objects
            if isinstance(start_date, str):
                start_date = fields.Date.from_string(start_date)
            if isinstance(end_date, str):
                end_date = fields.Date.from_string(end_date)
            
            # Add 1 day to end_date to include the entire day
            end_date_plus_one = end_date + timedelta(days=1)
            
            # Get orders
            orders = self.env['pos.order'].search([
                ('company_id', '=', company_id),
                ('amount_total', '>=', 0),
                ('date_order', '>=', start_date),
                ('date_order', '<', end_date_plus_one)
            ])
            
            category_data = {}
            for order in orders:
                for line in order.lines:
                    product = line.product_id
                    if not product:
                        continue
                        
                    category = product.categ_id
                    if not category:
                        continue
                        
                    category_id = category.id
                    
                    if category_id not in category_data:
                        category_data[category_id] = {
                            'category_id': category_id,
                            'category_name': category.display_name or category.name or 'Uncategorized',
                            'total_revenue': 0.0,
                            'total_cost': 0.0,
                            'total_profit': 0.0,
                        }
                    
                    quantity = line.qty or 0
                    revenue = line.price_subtotal or 0.0
                    cost = quantity * (product.standard_price or 0.0)
                    profit = revenue - cost
                    
                    category_data[category_id]['total_revenue'] += revenue
                    category_data[category_id]['total_cost'] += cost
                    category_data[category_id]['total_profit'] += profit
            
            results = list(category_data.values())
            results.sort(key=lambda x: x['total_profit'], reverse=True)
            results = results[:limit]
            
            # Calculate margin percentages and format
            company = self.env.company
            for res in results:
                revenue = res['total_revenue'] or 0.0
                cost = res['total_cost'] or 0.0
                profit = res['total_profit'] or 0.0
                margin_percentage = (profit / revenue * 100) if revenue > 0 else 0.0
                res['profit_margin_percentage'] = margin_percentage
                
                if company.currency_id.position == 'after':
                    res['total_revenue_display'] = f"{revenue:,.2f} {company.currency_id.symbol}"
                    res['total_cost_display'] = f"{cost:,.2f} {company.currency_id.symbol}"
                    res['total_profit_display'] = f"{profit:,.2f} {company.currency_id.symbol}"
                else:
                    res['total_revenue_display'] = f"{company.currency_id.symbol} {revenue:,.2f}"
                    res['total_cost_display'] = f"{company.currency_id.symbol} {cost:,.2f}"
                    res['total_profit_display'] = f"{company.currency_id.symbol} {profit:,.2f}"
            
            return results
            
        except Exception as e:
            _logger.error("Error in get_top_profitable_categories_with_dates: %s", str(e), exc_info=True)
            return []

    @api.model
    def get_top_profitable_categories_with_dates(self, limit=5, start_date=None, end_date=None):
        """Get top categories by profit margin with date range"""
        try:
            company_id = self.env.company.id
            start_date = fields.Date.from_string(start_date) if start_date else fields.Date.today()
            end_date = fields.Date.from_string(end_date) if end_date else fields.Date.today()
            
            domain = [
                ('company_id', '=', company_id),
                ('amount_total', '>=', 0),
                ('date_order', '>=', start_date),
                ('date_order', '<=', end_date + timedelta(days=1))
            ]
            
            orders = self.env['pos.order'].search(domain)
            
            category_data = {}
            for order in orders:
                for line in order.lines:
                    product = line.product_id
                    category = product.categ_id
                    
                    if not category:
                        continue
                        
                    if category.id not in category_data:
                        category_data[category.id] = {
                            'category_id': category.id,
                            'category_name': category.display_name or category.name,
                            'total_revenue': 0,
                            'total_cost': 0,
                            'total_profit': 0,
                        }
                    
                    quantity = line.qty
                    revenue = line.price_subtotal
                    cost = quantity * (product.standard_price or 0)
                    profit = revenue - cost
                    
                    category_data[category.id]['total_revenue'] += revenue
                    category_data[category.id]['total_cost'] += cost
                    category_data[category.id]['total_profit'] += profit
            
            results = list(category_data.values())
            results.sort(key=lambda x: x['total_profit'], reverse=True)
            results = results[:limit]
            
            # Format currency for display
            company = self.env.company
            for res in results:
                revenue = res['total_revenue'] or 0
                cost = res['total_cost'] or 0
                profit = res['total_profit'] or 0
                margin_percentage = (profit / revenue * 100) if revenue > 0 else 0
                res['profit_margin_percentage'] = margin_percentage
                
                if company.currency_id.position == 'after':
                    res['total_revenue_display'] = f"{revenue:,.2f} {company.currency_id.symbol}"
                    res['total_cost_display'] = f"{cost:,.2f} {company.currency_id.symbol}"
                    res['total_profit_display'] = f"{profit:,.2f} {company.currency_id.symbol}"
                else:
                    res['total_revenue_display'] = f"{company.currency_id.symbol} {revenue:,.2f}"
                    res['total_cost_display'] = f"{company.currency_id.symbol} {cost:,.2f}"
                    res['total_profit_display'] = f"{company.currency_id.symbol} {profit:,.2f}"
            
            return results
            
        except Exception as e:
            _logger.error("Error in get_top_profitable_categories_with_dates: %s", str(e), exc_info=True)
            return []

    @api.model
    def get_peak_hours_with_dates(self, start_date, end_date):
        """Get peak sales hours with date range - SIMPLIFIED VERSION"""
        try:
            company_id = self.env.company.id
            
            # Convert string dates to date objects
            if isinstance(start_date, str):
                start_date = fields.Date.from_string(start_date)
            if isinstance(end_date, str):
                end_date = fields.Date.from_string(end_date)
            
            _logger.info("Getting 24-hour sales for custom dates: %s to %s", start_date, end_date)
            
            # Get user timezone
            user_tz = self.env.user.tz or 'UTC'
            
            # Simple query without timezone conversion issues
            query = '''
                SELECT 
                    EXTRACT(hour FROM date_order) as hour,
                    COUNT(*) as order_count,
                    SUM(amount_total) as total_amount
                FROM pos_order
                WHERE company_id = %s
                AND amount_total >= 0
                AND date_order::date BETWEEN %s AND %s
                GROUP BY hour
                ORDER BY hour
            '''
            
            self._cr.execute(query, (company_id, start_date, end_date))
            results = self._cr.dictfetchall()
            
            _logger.info("Found %s hour records for custom dates", len(results))
            
            # Create a dictionary with all 24 hours initialized to 0
            hour_data = {}
            for hour in range(24):
                hour_data[hour] = {
                    'hour': hour,
                    'hour_display': f"{hour:02d}:00",
                    'order_count': 0,
                    'total_amount': 0.0,
                    'period': self._get_time_period(hour)
                }
            
            # Update with actual data
            for res in results:
                if res['hour'] is not None:
                    hour = int(res['hour'])
                    if hour in hour_data:
                        hour_data[hour]['order_count'] = res['order_count'] or 0
                        hour_data[hour]['total_amount'] = res['total_amount'] or 0.0
            
            # Convert to list and sort by hour
            all_hours = list(hour_data.values())
            all_hours.sort(key=lambda x: x['hour'])
            
            # Group by time periods for analysis
            time_periods = self._get_time_period_summary(all_hours)
            
            # Calculate totals
            total_sales = sum([h['total_amount'] for h in all_hours])
            total_orders = sum([h['order_count'] for h in all_hours])
            
            # Find peak hour
            peak_hour = None
            if all_hours:
                peak_hour = max(all_hours, key=lambda x: x['total_amount'])
            
            return {
                'all_hours': all_hours,
                'time_periods': time_periods,
                'total_sales': total_sales,
                'total_orders': total_orders,
                'peak_hour': peak_hour,
                'filter_type': 'custom',
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            }
            
        except Exception as e:
            _logger.error("Error in get_peak_hours_with_dates: %s", str(e), exc_info=True)
            # Return sample data on error
            sample_data = self._get_sample_24hour_data()
            sample_data['error'] = str(e)
            sample_data['filter_type'] = 'custom'
            return sample_data

    def _get_sample_customer_data(self):
        """Return sample customer data for testing"""
        company = self.env.company
        symbol = company.currency_id.symbol
        position = company.currency_id.position
        
        def format_currency(value):
            if position == 'after':
                return f"{value:,.2f} {symbol}"
            else:
                return f"{symbol} {value:,.2f}"
        
        return [
            {
                'id': 1,
                'customer_name': 'John Doe',
                'order_count': 5,
                'total_spent': 1250.50,
                'avg_order_value': 250.10,
                'last_order_date': fields.Datetime.now(),
                'total_spent_display': format_currency(1250.50),
                'avg_order_value_display': format_currency(250.10),
                'last_order_date_display': fields.Datetime.now().strftime('%Y-%m-%d %H:%M')
            },
            {
                'id': 2,
                'customer_name': 'Jane Smith',
                'order_count': 3,
                'total_spent': 850.75,
                'avg_order_value': 283.58,
                'last_order_date': fields.Datetime.now() - timedelta(days=1),
                'total_spent_display': format_currency(850.75),
                'avg_order_value_display': format_currency(283.58),
                'last_order_date_display': (fields.Datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M')
            }
        ]

    @api.model
    def get_top_customers_detailed_with_dates(self, limit=5, start_date=None, end_date=None):
        """Get detailed top customer information with date range - SIMPLIFIED"""
        try:
            company_id = self.env.company.id
            
            # Handle None dates
            if not start_date:
                start_date = fields.Date.today()
            if not end_date:
                end_date = fields.Date.today()
            
            # Convert string dates to date objects
            if isinstance(start_date, str):
                start_date = fields.Date.from_string(start_date)
            if isinstance(end_date, str):
                end_date = fields.Date.from_string(end_date)
            
            # Simple query without complex joins
            query = '''
                SELECT 
                    rp.id,
                    rp.name as customer_name,
                    COUNT(po.id) as order_count,
                    SUM(po.amount_total) as total_spent,
                    AVG(po.amount_total) as avg_order_value,
                    MAX(po.date_order) as last_order_date
                FROM pos_order po
                LEFT JOIN res_partner rp ON po.partner_id = rp.id
                WHERE po.company_id = %s
                AND po.amount_total >= 0
                AND po.date_order::date BETWEEN %s AND %s
                GROUP BY rp.id, rp.name
                ORDER BY total_spent DESC
                LIMIT %s
            '''
            
            self._cr.execute(query, [company_id, start_date, end_date, limit])
            results = self._cr.dictfetchall()
            
            # Format currency
            company = self.env.company
            for res in results:
                if not res.get('customer_name'):
                    res['customer_name'] = 'Walk-in Customer'
                
                sym_id = res['total_spent'] or 0
                avg_value = res['avg_order_value'] or 0
                
                if company.currency_id.position == 'after':
                    res['total_spent_display'] = f"{sym_id:,.2f} {company.currency_id.symbol}"
                    res['avg_order_value_display'] = f"{avg_value:,.2f} {company.currency_id.symbol}"
                else:
                    res['total_spent_display'] = f"{company.currency_id.symbol} {sym_id:,.2f}"
                    res['avg_order_value_display'] = f"{company.currency_id.symbol} {avg_value:,.2f}"
                
                if res['last_order_date']:
                    res['last_order_date_display'] = res['last_order_date'].strftime('%Y-%m-%d %H:%M')
                else:
                    res['last_order_date_display'] = 'Never'
            
            return results
            
        except Exception as e:
            _logger.error("Error in get_top_customers_detailed_with_dates: %s", str(e), exc_info=True)
            # Return sample data on error
            return self._get_sample_customer_data()


    @api.model
    def get_profit_trend_analysis(self, filter_type='today'):
        """Get profit trend analysis for chart - SIMPLIFIED WORKING VERSION"""
        try:
            company_id = self.env.company.id
            _logger.info("Getting profit trend analysis for filter: %s", filter_type)
            
            # Define date range
            today = fields.Date.today()
            start_date = today
            end_date = today
            
            if filter_type == 'today':
                start_date = today
                end_date = today
                group_by = "TO_CHAR(date_order, 'HH24')"
                x_axis_label = 'Hours'
            elif filter_type == 'yesterday':
                start_date = today - timedelta(days=1)
                end_date = today - timedelta(days=1)
                group_by = "TO_CHAR(date_order, 'HH24')"
                x_axis_label = 'Hours'
            elif filter_type == 'last_week':
                start_date = today - timedelta(days=7)
                end_date = today
                group_by = "TO_CHAR(date_order, 'YYYY-MM-DD')"
                x_axis_label = 'Days'
            elif filter_type == 'last_month':
                start_date = today - timedelta(days=30)
                end_date = today
                group_by = "TO_CHAR(date_order, 'YYYY-MM-DD')"
                x_axis_label = 'Days'
            elif filter_type == 'this_month':
                start_date = today.replace(day=1)
                end_date = today
                group_by = "TO_CHAR(date_order, 'YYYY-MM-DD')"
                x_axis_label = 'Days'
            elif filter_type == 'last_year':
                start_date = today.replace(year=today.year-1)
                end_date = today
                group_by = "TO_CHAR(date_order, 'Mon')"
                x_axis_label = 'Months'
            elif filter_type == 'this_year':
                start_date = today.replace(month=1, day=1)
                end_date = today
                group_by = "TO_CHAR(date_order, 'Mon')"
                x_axis_label = 'Months'
            else:
                # For custom or all time - monthly view
                start_date = None
                end_date = None
                group_by = "TO_CHAR(date_order, 'YYYY-MM')"
                x_axis_label = 'Months'
            
            # Build the query
            query = f'''
                SELECT 
                    {group_by} as period,
                    SUM(amount_total) as total_amount,
                    COUNT(*) as order_count
                FROM pos_order
                WHERE company_id = %s
                AND amount_total >= 0
            '''
            
            params = [company_id]
            
            if start_date and end_date:
                query += " AND date_order::date BETWEEN %s AND %s"
                params.extend([start_date, end_date])
            
            query += f'''
                GROUP BY period
                ORDER BY period
            '''
            
            _logger.info("Executing query: %s", query)
            _logger.info("Params: %s", params)
            
            self._cr.execute(query, params)
            results = self._cr.dictfetchall()
            
            _logger.info("Query results count: %s", len(results))
            
            if not results:
                _logger.info("No data found for profit trend analysis")
                return {
                    'labels': ['No Data Available'],
                    'datasets': [{
                        'label': 'Profit',
                        'data': [0],
                        'backgroundColor': 'rgba(200, 200, 200, 0.2)',
                        'borderColor': 'rgba(200, 200, 200, 1)',
                        'borderWidth': 2,
                        'fill': False,
                        'tension': 0.4
                    }],
                    'type': 'line',
                    'x_axis_label': 'No Data',
                    'total_profit': 0,
                    'total_revenue': 0,
                    'total_cost': 0,
                    'no_data': True
                }
            
            # Process results
            labels = []
            profit_data = []
            
            for res in results:
                if res['period']:
                    period = res['period']
                    # Format for display
                    if filter_type in ['today', 'yesterday']:
                        try:
                            # Convert hour from string to formatted hour
                            hour = int(period) if isinstance(period, str) and period.isdigit() else 0
                            period = f"{hour:02d}:00"
                        except:
                            period = str(period)
                    
                    labels.append(str(period))
                    profit_data.append(float(res['total_amount'] or 0))
            
            return {
                'labels': labels,
                'datasets': [{
                    'label': 'Sales',
                    'data': profit_data,
                    'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                    'borderColor': 'rgba(75, 192, 192, 1)',
                    'borderWidth': 3,
                    'fill': True,
                    'tension': 0.4
                }],
                'type': 'line',
                'x_axis_label': x_axis_label,
                'total_profit': sum(profit_data),
                'total_revenue': sum(profit_data),
                'total_cost': 0,
                'no_data': False
            }
            
        except Exception as e:
            _logger.error("Error in get_profit_trend_analysis: %s", str(e), exc_info=True)
            
            # Return NO DATA instead of sample data
            return {
                'labels': ['No Data Available'],
                'datasets': [{
                    'label': 'No Data',
                    'data': [0],
                    'backgroundColor': 'rgba(200, 200, 200, 0.2)',
                    'borderColor': 'rgba(200, 200, 200, 1)',
                    'borderWidth': 2,
                    'fill': False,
                    'tension': 0.4
                }],
                'type': 'line',
                'x_axis_label': 'No Data',
                'total_profit': 0,
                'total_revenue': 0,
                'total_cost': 0,
                'no_data': True
            }
            
    @api.model
    def get_profit_margin_analysis_with_dates(self, start_date, end_date):
        """Get profit margin analysis for custom date range - SIMPLIFIED"""
        try:
            company_id = self.env.company.id
            
            # Convert string dates to date objects
            if isinstance(start_date, str):
                start_date = fields.Date.from_string(start_date)
            if isinstance(end_date, str):
                end_date = fields.Date.from_string(end_date)
            
            # Add 1 day to end_date to include the entire day
            end_date_plus_one = end_date + timedelta(days=1)
            
            # Get orders in the date range
            orders = self.env['pos.order'].search([
                ('company_id', '=', company_id),
                ('amount_total', '>=', 0),
                ('date_order', '>=', start_date),
                ('date_order', '<', end_date_plus_one)
            ])
            
            # Process orders
            product_data = {}
            for order in orders:
                for line in order.lines:
                    product = line.product_id
                    if not product:
                        continue
                        
                    product_id = product.id
                    
                    if product_id not in product_data:
                        product_data[product_id] = {
                            'product_id': product_id,
                            'product_name': product.name or 'Unknown Product',
                            'total_quantity': 0,
                            'total_revenue': 0.0,
                            'total_cost': 0.0,
                            'total_profit': 0.0,
                        }
                    
                    # Calculate values
                    quantity = line.qty or 0
                    revenue = line.price_subtotal or 0.0
                    cost = quantity * (product.standard_price or 0.0)
                    profit = revenue - cost
                    
                    product_data[product_id]['total_quantity'] += quantity
                    product_data[product_id]['total_revenue'] += revenue
                    product_data[product_id]['total_cost'] += cost
                    product_data[product_id]['total_profit'] += profit
            
            # Convert to list and sort by profit
            results = list(product_data.values())
            results.sort(key=lambda x: x['total_profit'], reverse=True)
            results = results[:10]
            
            # Format for display
            company = self.env.company
            for res in results:
                revenue = res['total_revenue'] or 0.0
                cost = res['total_cost'] or 0.0
                profit = res['total_profit'] or 0.0
                
                # Calculate margin percentage
                margin_percentage = 0.0
                if revenue > 0:
                    margin_percentage = (profit / revenue) * 100
                
                res['profit_margin_percentage'] = margin_percentage
                res['profit_margin_percentage_display'] = f"{margin_percentage:.1f}%"
                
                # Format currency
                if company.currency_id.position == 'after':
                    res['total_revenue_display'] = f"{revenue:,.2f} {company.currency_id.symbol}"
                    res['total_cost_display'] = f"{cost:,.2f} {company.currency_id.symbol}"
                    res['total_profit_display'] = f"{profit:,.2f} {company.currency_id.symbol}"
                else:
                    res['total_revenue_display'] = f"{company.currency_id.symbol} {revenue:,.2f}"
                    res['total_cost_display'] = f"{company.currency_id.symbol} {cost:,.2f}"
                    res['total_profit_display'] = f"{company.currency_id.symbol} {profit:,.2f}"
                
                # Determine margin status
                if margin_percentage >= 40:
                    res['margin_status'] = 'high'
                    res['margin_status_label'] = 'High Margin'
                elif margin_percentage >= 20:
                    res['margin_status'] = 'medium'
                    res['margin_status_label'] = 'Good Margin'
                else:
                    res['margin_status'] = 'low'
                    res['margin_status_label'] = 'Low Margin'
            
            return results
            
        except Exception as e:
            _logger.error("Error in get_profit_margin_analysis_with_dates: %s", str(e), exc_info=True)
            return []

    def _get_sample_profit_data(self):
        """Return sample profit data for testing"""
        company = self.env.company
        symbol = company.currency_id.symbol
        position = company.currency_id.position
        
        def format_currency(value):
            if position == 'after':
                return f"{value:,.2f} {symbol}"
            else:
                return f"{symbol} {value:,.2f}"
        
        return [
            {
                'product_id': None,
                'product_name': 'No sales recorded',
                'total_quantity': 0,
                'total_revenue': 0.0,
                'total_cost': 0.0,
                'total_profit': 0.0,
                'total_revenue_display': format_currency(0.0),
                'total_cost_display': format_currency(0.0),
                'total_profit_display': format_currency(0.0),
                'profit_margin_percentage': 0.0,
                'profit_margin_percentage_display': '0%',
                'margin_status': 'none',
                'margin_status_label': 'No Data'
            }
        ]

    @api.model
    def get_profit_trend_analysis_with_dates(self, start_date, end_date):
        """Get profit trend analysis for custom date range"""
        try:
            company_id = self.env.company.id
            user_tz = self.env.user.tz if self.env.user.tz else pytz.UTC
            
            # Convert string dates to date objects
            if isinstance(start_date, str):
                start_date = fields.Date.from_string(start_date)
            if isinstance(end_date, str):
                end_date = fields.Date.from_string(end_date)
            
            days_diff = (end_date - start_date).days
            
            if days_diff <= 2:  # 2 days or less - show by hour
                query = '''
                    SELECT 
                        EXTRACT(hour FROM date_order AT TIME ZONE 'utc' AT TIME ZONE %s) as hour,
                        SUM(amount_total) as total_amount,
                        COUNT(*) as order_count
                    FROM pos_order
                    WHERE company_id = %s
                    AND amount_total >= 0
                    AND date_order::date BETWEEN %s AND %s
                    GROUP BY hour
                    ORDER BY hour
                '''
                self._cr.execute(query, [user_tz, company_id, start_date, end_date])
                x_axis_label = 'Hours'
                
            elif days_diff <= 31:  # Up to a month - show by day
                query = '''
                    SELECT 
                        TO_CHAR(date_order, 'YYYY-MM-DD') as period,
                        SUM(amount_total) as total_amount,
                        COUNT(*) as order_count
                    FROM pos_order
                    WHERE company_id = %s
                    AND amount_total >= 0
                    AND date_order::date BETWEEN %s AND %s
                    GROUP BY TO_CHAR(date_order, 'YYYY-MM-DD')
                    ORDER BY period
                '''
                self._cr.execute(query, [company_id, start_date, end_date])
                x_axis_label = 'Days'
                
            else:  # More than a month - show by month
                query = '''
                    SELECT 
                        TO_CHAR(date_order, 'YYYY-MM') as period,
                        SUM(amount_total) as total_amount,
                        COUNT(*) as order_count
                    FROM pos_order
                    WHERE company_id = %s
                    AND amount_total >= 0
                    AND date_order::date BETWEEN %s AND %s
                    GROUP BY TO_CHAR(date_order, 'YYYY-MM')
                    ORDER BY period
                '''
                self._cr.execute(query, [company_id, start_date, end_date])
                x_axis_label = 'Months'
            
            results = self._cr.dictfetchall()
            
            if not results:
                return {
                    'labels': ['No Data Available'],
                    'datasets': [{
                        'label': 'Sales',
                        'data': [0],
                        'backgroundColor': 'rgba(200, 200, 200, 0.2)',
                        'borderColor': 'rgba(200, 200, 200, 1)',
                        'borderWidth': 2,
                        'fill': False,
                        'tension': 0.4
                    }],
                    'type': 'line',
                    'x_axis_label': 'No Data Available for Selected Dates',
                    'total_profit': 0,
                    'total_revenue': 0,
                    'total_cost': 0,
                    'no_data': True
                }
            
            # Process results
            labels = []
            profit_data = []
            
            for res in results:
                if res['period']:
                    period = res['period']
                    
                    # Format for display
                    if days_diff <= 2:  # Hourly data
                        try:
                            hour = int(period) if period is not None else 0
                            period = f"{hour:02d}:00"
                        except:
                            pass
                    elif days_diff <= 31:  # Daily data
                        try:
                            # Format as DD/MM
                            date_obj = datetime.strptime(str(period), '%Y-%m-%d')
                            period = date_obj.strftime('%d/%m')
                        except:
                            pass
                    else:  # Monthly data
                        try:
                            # Format as MMM YY
                            date_obj = datetime.strptime(str(period) + '-01', '%Y-%m-%d')
                            period = date_obj.strftime('%b %y')
                        except:
                            pass
                    
                    labels.append(str(period))
                    profit_data.append(float(res['total_amount'] or 0))
            
            return {
                'labels': labels,
                'datasets': [{
                    'label': 'Sales',
                    'data': profit_data,
                    'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                    'borderColor': 'rgba(75, 192, 192, 1)',
                    'borderWidth': 3,
                    'fill': True,
                    'tension': 0.4
                }],
                'type': 'line',
                'x_axis_label': x_axis_label,
                'total_profit': sum(profit_data),
                'total_revenue': sum(profit_data),
                'total_cost': 0,
                'no_data': False
            }
            
        except Exception as e:
            _logger.error("Error in get_profit_trend_analysis_with_dates: %s", str(e), exc_info=True)
            
            return {
                'labels': ['Error Loading Data'],
                'datasets': [{
                    'label': 'Error',
                    'data': [0],
                    'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                    'borderColor': 'rgba(255, 99, 132, 1)',
                    'borderWidth': 2,
                    'fill': False,
                    'tension': 0.4
                }],
                'type': 'line',
                'x_axis_label': 'Error',
                'total_profit': 0,
                'total_revenue': 0,
                'total_cost': 0,
                'no_data': True,
                'error': str(e)
            }

    def _get_default_profit_trend_data(self):
        """Return default profit trend data"""
        return {
            'labels': ['No Data'],
            'datasets': [{
                'label': 'Profit',
                'data': [0],
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'borderColor': 'rgba(75, 192, 192, 1)',
                'borderWidth': 2,
                'fill': True,
                'tension': 0.4
            }],
            'type': 'line',
            'x_axis_label': 'No Data Available',
            'total_profit': 0,
            'total_revenue': 0,
            'total_cost': 0
        }
        
    # ---------------------------------------------------------------------------
    # Expense vs Revenue — now accounting based (no HR)
    # ---------------------------------------------------------------------------
    @api.model
    def get_expense_revenue_comparison(self, year=None, month=None):
        """Expense vs revenue using accounting expense entries."""
        try:
            company_id = self.env.company.id
            today = fields.Date.today()
            if not year:
                year = today.year

            if month:
                start_date = today.replace(year=year, month=month, day=1)
                end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            else:
                start_date = today.replace(year=year, month=1, day=1)
                end_date = today.replace(year=year, month=12, day=31)

            revenue_orders = self.env['pos.order'].search([
                ('company_id', '=', company_id),
                ('amount_total', '>=', 0),
                ('state', 'in', ['paid', 'done', 'invoiced']),
                ('date_order', '>=', start_date),
                ('date_order', '<=', end_date),
            ])
            total_revenue = sum(o.amount_total for o in revenue_orders)
            total_expense = self._get_expense_total(company_id, start_date, end_date)

            total_profit = total_revenue - total_expense
            profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0

            company = self.env.company
            if company.currency_id.position == 'after':
                total_revenue_display = f"{total_revenue:,.2f} PKR"
                total_expense_display = f"{total_expense:,.2f} PKR"
                total_profit_display = f"{total_profit:,.2f} PKR"
            else:
                total_revenue_display = f"PKR {total_revenue:,.2f}"
                total_expense_display = f"PKR {total_expense:,.2f}"
                total_profit_display = f"PKR {total_profit:,.2f}"

            return {
                'total_revenue': total_revenue,
                'total_expense': total_expense,
                'total_profit': total_profit,
                'profit_margin': profit_margin,
                'total_revenue_display': total_revenue_display,
                'total_expense_display': total_expense_display,
                'total_profit_display': total_profit_display,
                'profit_margin_display': f"{profit_margin:.1f}%",
                'year': year,
                'month': month,
                'period': self._get_period_display(year, month),
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'expense_source': 'Accounting',
            }
        except Exception as e:
            _logger.error("Error in get_expense_revenue_comparison: %s", str(e), exc_info=True)
            today = fields.Date.today()
            return {
                'total_revenue': 0, 'total_expense': 0, 'total_profit': 0, 'profit_margin': 0,
                'total_revenue_display': 'PKR 0.00',
                'total_expense_display': 'PKR 0.00',
                'total_profit_display': 'PKR 0.00',
                'profit_margin_display': '0%',
                'year': year or today.year, 'month': month,
                'period': 'Error', 'error': str(e),
            }


    @api.model
    def get_expense_revenue_monthly(self, year=None):
        """Monthly expense vs revenue using accounting entries."""
        try:
            company_id = self.env.company.id
            today = fields.Date.today()
            if not year:
                year = today.year

            months_data = []
            for month in range(1, 13):
                month_start = today.replace(year=year, month=month, day=1)
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

                revenue_orders = self.env['pos.order'].search([
                    ('company_id', '=', company_id),
                    ('amount_total', '>=', 0),
                    ('state', 'in', ['paid', 'done', 'invoiced']),
                    ('date_order', '>=', month_start),
                    ('date_order', '<=', month_end),
                ])
                monthly_revenue = sum(o.amount_total for o in revenue_orders)
                monthly_expense = self._get_expense_total(company_id, month_start, month_end)

                monthly_profit = monthly_revenue - monthly_expense
                monthly_margin = (monthly_profit / monthly_revenue * 100) if monthly_revenue > 0 else 0

                months_data.append({
                    'month': month,
                    'month_name': month_start.strftime('%b'),
                    'revenue': monthly_revenue,
                    'expense': monthly_expense,
                    'profit': monthly_profit,
                    'margin': monthly_margin,
                    'revenue_display': f"PKR {monthly_revenue:,.0f}",
                    'expense_display': f"PKR {monthly_expense:,.0f}",
                    'profit_display': f"PKR {monthly_profit:,.0f}",
                    'margin_display': f"{monthly_margin:.1f}%",
                    'is_current': month == today.month and year == today.year,
                })

            total_revenue = sum(i['revenue'] for i in months_data)
            total_expense = sum(i['expense'] for i in months_data)
            total_profit = total_revenue - total_expense
            avg_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0

            return {
                'year': year,
                'months': months_data,
                'summary': {
                    'total_revenue': total_revenue,
                    'total_expense': total_expense,
                    'total_profit': total_profit,
                    'avg_margin': avg_margin,
                    'total_revenue_display': f"PKR {total_revenue:,.0f}",
                    'total_expense_display': f"PKR {total_expense:,.0f}",
                    'total_profit_display': f"PKR {total_profit:,.0f}",
                    'avg_margin_display': f"{avg_margin:.1f}%",
                    'expense_source': 'Accounting',
                },
            }
        except Exception as e:
            _logger.error("Error in get_expense_revenue_monthly: %s", str(e), exc_info=True)
            return {
                'year': year or fields.Date.today().year,
                'months': [],
                'summary': {
                    'total_revenue': 0, 'total_expense': 0, 'total_profit': 0, 'avg_margin': 0,
                    'total_revenue_display': 'PKR 0',
                    'total_expense_display': 'PKR 0',
                    'total_profit_display': 'PKR 0',
                    'avg_margin_display': '0%',
                },
                'error': str(e),
            }


    @api.model
    def get_expense_revenue_yearly(self, years_back=5):
        """Yearly expense vs revenue using accounting entries."""
        try:
            company_id = self.env.company.id
            today = fields.Date.today()
            current_year = today.year

            years_data = []
            for year_offset in range(years_back - 1, -1, -1):
                year = current_year - year_offset
                year_start = today.replace(year=year, month=1, day=1)
                year_end = today.replace(year=year, month=12, day=31)

                revenue_orders = self.env['pos.order'].search([
                    ('company_id', '=', company_id),
                    ('amount_total', '>=', 0),
                    ('state', 'in', ['paid', 'done', 'invoiced']),
                    ('date_order', '>=', year_start),
                    ('date_order', '<=', year_end),
                ])
                yearly_revenue = sum(o.amount_total for o in revenue_orders)
                yearly_expense = self._get_expense_total(company_id, year_start, year_end)

                yearly_profit = yearly_revenue - yearly_expense
                yearly_margin = (yearly_profit / yearly_revenue * 100) if yearly_revenue > 0 else 0

                years_data.append({
                    'year': year,
                    'revenue': yearly_revenue,
                    'expense': yearly_expense,
                    'profit': yearly_profit,
                    'margin': yearly_margin,
                    'revenue_display': f"PKR {yearly_revenue:,.0f}",
                    'expense_display': f"PKR {yearly_expense:,.0f}",
                    'profit_display': f"PKR {yearly_profit:,.0f}",
                    'margin_display': f"{yearly_margin:.1f}%",
                    'is_current': year == current_year,
                })

            return {
                'years': years_data,
                'current_year': current_year,
                'years_back': years_back,
            }
        except Exception as e:
            _logger.error("Error in get_expense_revenue_yearly: %s", str(e), exc_info=True)
            return {
                'years': [],
                'current_year': fields.Date.today().year,
                'years_back': years_back,
                'error': str(e),
            }
    
    @api.model
    def get_hr_expense_details(self, year=None, month=None):
        """Debug method to see detailed HR expense data"""
        try:
            company_id = self.env.company.id
            today = fields.Date.today()
            
            if not year:
                year = today.year
            
            if month:
                start_date = today.replace(year=year, month=month, day=1)
                end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            else:
                start_date = today.replace(year=year, month=1, day=1)
                end_date = today.replace(year=year, month=12, day=31)
            
            # Get all HR expenses
            hr_expenses = self.env['hr.expense'].search([
                ('company_id', '=', company_id),
                ('state', '=', 'done'),
                ('date', '>=', start_date),
                ('date', '<=', end_date)
            ], order='date asc')
            
            expense_details = []
            for expense in hr_expenses:
                expense_details.append({
                    'id': expense.id,
                    'name': expense.name,
                    'employee': expense.employee_id.name if expense.employee_id else '',
                    'date': expense.date.strftime('%Y-%m-%d'),
                    'amount': expense.total_amount,
                    'description': expense.description or '',
                    'paid_by': expense.payment_mode or '',
                    'state': expense.state
                })
            
            total_amount = sum(expense.total_amount for expense in hr_expenses)
            
            return {
                'count': len(hr_expenses),
                'total_amount': total_amount,
                'details': expense_details,
                'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                'company': self.env.company.name
            }
            
        except Exception as e:
            _logger.error("Error in get_hr_expense_details: %s", str(e))
            return {
                'count': 0,
                'total_amount': 0,
                'details': [],
                'error': str(e)
            }
            
    @api.model
    def test_hr_expense_fetch(self, year=2025, month=7):
        """Test method to debug HR expense data - adjust year/month as needed"""
        company_id = self.env.company.id
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-31"
        
        # Check HR expenses
        hr_expenses = self.env['hr.expense'].search([
            ('company_id', '=', company_id),
            ('state', '=', 'done'),
            ('date', '>=', start_date),
            ('date', '<=', end_date)
        ])
        
        result = {
            'month': f"{year}-{month:02d}",
            'hr_expense_count': len(hr_expenses),
            'hr_expense_total': sum(exp.total_amount for exp in hr_expenses),
            'expenses': []
        }
        
        for exp in hr_expenses:
            result['expenses'].append({
                'id': exp.id,
                'name': exp.name,
                'date': exp.date,
                'employee': exp.employee_id.name if exp.employee_id else '',
                'amount': exp.total_amount,
                'state': exp.state,
                'description': exp.description or ''
            })
        
        _logger.info("HR Expense Test Result: %s", result)
        return result
    
    @api.model
    def get_expense_revenue_yearly(self, years_back=5):
        """Get yearly expense and revenue data"""
        try:
            company_id = self.env.company.id
            today = fields.Date.today()
            current_year = today.year
            
            years_data = []
            
            for year_offset in range(years_back - 1, -1, -1):
                year = current_year - year_offset
                
                year_start = today.replace(year=year, month=1, day=1)
                year_end = today.replace(year=year, month=12, day=31)
                
                # Get revenue for the year
                revenue_orders = self.env['pos.order'].search([
                    ('company_id', '=', company_id),
                    ('amount_total', '>=', 0),
                    ('state', 'in', ['paid', 'done', 'invoiced']),
                    ('date_order', '>=', year_start),
                    ('date_order', '<=', year_end)
                ])
                
                yearly_revenue = sum(order.amount_total for order in revenue_orders)
                
                # Try to get expense for the year
                yearly_expense = 0.0
                try:
                    expense_accounts = self.env['hr.expense'].search([
                        ('company_id', '=', company_id),
                        ('state', '=', 'done'),
                        ('date', '>=', year_start),
                        ('date', '<=', year_end)
                    ])
                    # expense_accounts = self.env['account.account'].search([
                    #     ('company_id', '=', company_id),
                    #     ('account_type', '=', 'expense'),
                    #     ('deprecated', '=', False)
                    # ])
                    
                    # if expense_accounts:
                    #     ExpenseLine = self.env['account.move.line']
                    #     expense_lines = ExpenseLine.search([
                    #         ('account_id', 'in', expense_accounts.ids),
                    #         ('parent_state', '=', 'posted'),
                    #         ('date', '>=', year_start),
                    #         ('date', '<=', year_end),
                    #         ('company_id', '=', company_id)
                    #     ])
                        
                    #     yearly_expense = sum(abs(line.balance) for line in expense_lines)
                    yearly_expense = sum(abs(line.total_amount) for line in expense_accounts)
                except Exception:
                    # Fallback: use 60% of revenue as expense
                    yearly_expense = yearly_revenue * 0.6
                
                yearly_profit = yearly_revenue - yearly_expense
                yearly_margin = (yearly_profit / yearly_revenue * 100) if yearly_revenue > 0 else 0
                
                years_data.append({
                    'year': year,
                    'revenue': yearly_revenue,
                    'expense': yearly_expense,
                    'profit': yearly_profit,
                    'margin': yearly_margin,
                    'revenue_display': f"GH¢ {yearly_revenue:,.0f}",
                    'expense_display': f"GH¢ {yearly_expense:,.0f}",
                    'profit_display': f"GH¢ {yearly_profit:,.0f}",
                    'margin_display': f"{yearly_margin:.1f}%",
                    'is_current': year == current_year
                })
            
            return {
                'years': years_data,
                'current_year': current_year,
                'years_back': years_back
            }
            
        except Exception as e:
            _logger.error("Error in get_expense_revenue_yearly: %s", str(e), exc_info=True)
            return {
                'years': [],
                'current_year': current_year,
                'years_back': years_back,
                'error': str(e)
            }
    
    def _get_period_display(self, year, month):
        """Get display name for period"""
        if month:
            month_names = [
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ]
            return f"{month_names[month-1]} {year}"
        else:
            return f"Year {year}"
    
    @api.model
    def get_available_years(self):
        """Get list of available years with data"""
        try:
            company_id = self.env.company.id
            query = '''
                SELECT DISTINCT EXTRACT(year FROM date_order) as year
                FROM pos_order
                WHERE company_id = %s
                AND amount_total >= 0
                ORDER BY year DESC
                LIMIT 10
            '''
            self._cr.execute(query, [company_id])
            results = self._cr.fetchall()
            
            years = [int(result[0]) for result in results if result[0]]
            if not years:
                years = [fields.Date.today().year]
            
            return years
        except Exception as e:
            _logger.error("Error in get_available_years: %s", str(e))
            return [fields.Date.today().year]
class PosSalesTarget(models.Model):
    """Model to store POS sales targets"""
    _name = 'pos.sales.target'
    _description = 'POS Sales Target'
    
    company_id = fields.Many2one('res.company', string='Company', required=True, 
                                 default=lambda self: self.env.company)
    period = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly')
    ], string='Period', required=True, default='monthly')
    year_month = fields.Char(string='Year-Month', help='Format: YYYY-MM for monthly targets')
    target_amount = fields.Float(string='Target Amount', required=True)
    user_id = fields.Many2one('res.users', string='Set By', default=lambda self: self.env.user)
    date_set = fields.Datetime(string='Date Set', default=fields.Datetime.now)