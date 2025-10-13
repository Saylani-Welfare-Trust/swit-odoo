import io
import json
import calendar
from dateutil.relativedelta import relativedelta
import xlsxwriter
from odoo import api, fields, models
from datetime import datetime
from odoo.tools import date_utils


class AccountGeneralLedger(models.TransientModel):
    """For creating General Ledger report"""
    _inherit = 'account.general.ledger'

    @api.model
    def view_report(self, option, tag, selected_analytic_plan_list):
        print(selected_analytic_plan_list, 'selected_analytic_plan_list view report')
        """
        Retrieve partner ledger report data based on options and tags.

        :param option: The options to filter the report data.
        :type option: str

        :param tag: The tag to filter the report data.
        :type tag: str

        :return: A dictionary containing the partner ledger report data.
        :rtype: dict
        """
        account_dict = {}
        account_totals = {}
        move_line_ids = self.env['account.move.line'].search(
            [('parent_state', '=', 'posted')])
        account_ids = move_line_ids.mapped('account_id')
        account_dict['journal_ids'] = self.env['account.journal'].search_read(
            [], ['name'])

        account_dict['analytic_plan_ids'] = self.env['account.analytic.plan'].search_read([('parent_id', '=', False)], ['name'])

        account_dict['analytic_ids'] = self.env[
            'account.analytic.account'].search_read(
            [('plan_id', 'in', selected_analytic_plan_list)], ['name'])
        for account in account_ids:
            move_line_id = move_line_ids.filtered(
                lambda x: x.account_id == account)
            move_line_list = []
            for move_line in move_line_id:
                move_line_data = move_line.read(
                    ['date', 'name', 'move_name', 'debit', 'credit',
                     'partner_id', 'account_id', 'journal_id', 'move_id',
                     'analytic_line_ids'])
                move_line_list.append(move_line_data)
            account_dict[account.display_name] = move_line_list
            currency_id = self.env.company.currency_id.symbol
            account_totals[account.display_name] = {
                'total_debit': round(sum(move_line_id.mapped('debit')), 2),
                'total_credit': round(sum(move_line_id.mapped('credit')), 2),
                'currency_id': currency_id,
                'account_id': account.id}
            account_dict['account_totals'] = account_totals
        return account_dict

    @api.model
    def get_filter_values(self, journal_id, date_range, options, analytic, method, selected_analytic_plan_list):
        """
        Retrieve filtered values for the partner ledger report.

        :param journal_id: The journal IDs to filter the report data.
        :type journal_id: list

        :param date_range: The date range option to filter the report data.
        :type date_range: str or dict

        :param options: The additional options to filter the report data.
        :type options: dict

        :param method: Find the method
        :type options: dict

        :param analytic: The analytic IDs to filter the report data.
        :type analytic: list

        :return: A dictionary containing the filtered values for the partner
        ledger report.
        :rtype: dict
        """
        account_dict = {}
        account_totals = {}
        today = fields.Date.today()
        quarter_start, quarter_end = date_utils.get_quarter(today)
        previous_quarter_start = quarter_start - relativedelta(months=3)
        previous_quarter_end = quarter_start - relativedelta(days=1)
        if options == {}:
            options = None
        if options is None:
            option_domain = ['posted']
        elif 'draft' in options:
            option_domain = ['posted', 'draft']
        domain = [('journal_id', 'in', journal_id),
                  ('parent_state', 'in', option_domain), ] if journal_id else [
            ('parent_state', 'in', option_domain), ]
        if method == {}:
            method = None
        if method is not None and 'cash' in method:
            domain += [('journal_id', 'in',
                        self.env.company.tax_cash_basis_journal_id.ids), ]
        if analytic:
            analytic_line = self.env['account.analytic.line'].search(
                [('account_id', 'in', analytic)]).mapped('id')
            domain += [('analytic_line_ids', 'in', analytic_line)]
        if date_range:
            if date_range == 'month':
                domain += [('date', '>=', today.replace(day=1)),
                           ('date', '<=', today)]
            elif date_range == 'year':
                domain += [('date', '>=', today.replace(month=1, day=1)),
                           ('date', '<=', today)]
            elif date_range == 'quarter':
                domain += [('date', '>=', quarter_start),
                           ('date', '<=', quarter_end)]
            elif date_range == 'last-month':
                last_month_start = today.replace(day=1) - relativedelta(
                    months=1)
                last_month_end = last_month_start + relativedelta(
                    day=calendar.monthrange(last_month_start.year,
                                            last_month_start.month)[
                        1])
                domain += [('date', '>=', last_month_start),
                           ('date', '<=', last_month_end)]
            elif date_range == 'last-year':
                last_year_start = today.replace(month=1,
                                                day=1) - relativedelta(years=1)
                last_year_end = last_year_start.replace(month=12, day=31)
                domain += [('date', '>=', last_year_start),
                           ('date', '<=', last_year_end)]
            elif date_range == 'last-quarter':
                domain += [('date', '>=', previous_quarter_start),
                           ('date', '<=', previous_quarter_end)]
            elif 'start_date' in date_range and 'end_date' in date_range:
                start_date = datetime.strptime(date_range['start_date'],
                                               '%Y-%m-%d').date()
                end_date = datetime.strptime(date_range['end_date'],
                                             '%Y-%m-%d').date()
                domain += [('date', '>=', start_date),
                           ('date', '<=', end_date)]
            elif 'start_date' in date_range:
                start_date = datetime.strptime(date_range['start_date'],
                                               '%Y-%m-%d').date()
                domain += [('date', '>=', start_date)]
            elif 'end_date' in date_range:
                end_date = datetime.strptime(date_range['end_date'],
                                             '%Y-%m-%d').date()
                domain += [('date', '<=', end_date)]
        move_line_ids = self.env['account.move.line'].search(domain)
        account_ids = move_line_ids.mapped('account_id')
        account_dict['journal_ids'] = self.env['account.journal'].search_read(
            [], ['name'])

        account_dict['analytic_plan_ids'] = self.env['account.analytic.plan'].search_read([('parent_id', '=', False)],
                                                                                          ['name'])

        account_dict['analytic_ids'] = self.env[
            'account.analytic.account'].search_read(
            [('plan_id', 'in', selected_analytic_plan_list)], ['name'])
        for account in account_ids:
            move_line_id = move_line_ids.filtered(
                lambda x: x.account_id == account)
            move_line_list = []
            for move_line in move_line_id:
                move_line_data = move_line.read(
                    ['date', 'name', 'move_name', 'debit', 'credit',
                     'partner_id', 'account_id', 'journal_id', 'move_id',
                     'analytic_line_ids'])
                move_line_list.append(move_line_data)
            account_dict[account.display_name] = move_line_list
            currency_id = self.env.company.currency_id.symbol
            account_totals[account.display_name] = {
                'total_debit': round(sum(move_line_id.mapped('debit')), 2),
                'total_credit': round(sum(move_line_id.mapped('credit')), 2),
                'currency_id': currency_id,
                'account_id': account.id}
            account_dict['account_totals'] = account_totals
        return account_dict