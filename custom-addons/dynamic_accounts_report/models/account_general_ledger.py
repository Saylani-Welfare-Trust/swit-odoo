# -*- coding: utf-8 -*-
################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Ammu Raj (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
################################################################################
import io
import json
import calendar
from collections import defaultdict
from dateutil.relativedelta import relativedelta
import xlsxwriter
from odoo import api, fields, models
from datetime import datetime
from odoo.tools import date_utils


class AccountGeneralLedger(models.TransientModel):
    """For creating General Ledger report"""
    _name = 'account.general.ledger'
    _description = 'General Ledger Report'

    @api.model
    def view_report(self, option, tag):
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
        move_lines = self.env['account.move.line'].search_read(
            [('parent_state', '=', 'posted')],
            ['date', 'name', 'move_name', 'debit', 'credit',
             'partner_id', 'account_id', 'journal_id', 'move_id',
             'analytic_line_ids']
        )

        account_dict['journal_ids'] = self.env['account.journal'].search_read([], ['name'])
        account_dict['analytic_ids'] = self.env['account.analytic.account'].search_read([], ['name'])

        entries_by_account = defaultdict(list)
        account_totals = {}
        account_map = {}
        account_ids = {line['account_id'][0] for line in move_lines if line.get('account_id')}
        if account_ids:
            account_map = {account.id: account.display_name for account in self.env['account.account'].browse(list(account_ids))}

        for line in move_lines:
            account_id = line.get('account_id')
            if not account_id:
                continue
            account_key = account_map.get(account_id[0], account_id[1])
            entries_by_account[account_key].append(line)
            totals = account_totals.setdefault(
                account_key,
                {'total_debit': 0.0, 'total_credit': 0.0, 'currency_id': self.env.company.currency_id.symbol, 'account_id': account_id[0]}
            )
            totals['total_debit'] += line.get('debit') or 0.0
            totals['total_credit'] += line.get('credit') or 0.0

        for account_key, lines in entries_by_account.items():
            account_dict[account_key] = lines

        account_dict['account_totals'] = account_totals
        return account_dict

    @api.model
    def get_filter_values(self, journal_id, date_range, options, analytic,
                          method):
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
        move_lines = self.env['account.move.line'].search_read(
            domain,
            ['date', 'name', 'move_name', 'debit', 'credit',
             'partner_id', 'account_id', 'journal_id', 'move_id',
             'analytic_line_ids']
        )

        account_dict['journal_ids'] = self.env['account.journal'].search_read([], ['name'])
        account_dict['analytic_ids'] = self.env['account.analytic.account'].search_read([], ['name'])

        entries_by_account = defaultdict(list)
        account_map = {}
        account_ids = {line['account_id'][0] for line in move_lines if line.get('account_id')}
        if account_ids:
            account_map = {account.id: account.display_name for account in self.env['account.account'].browse(list(account_ids))}

        for line in move_lines:
            account_id = line.get('account_id')
            if not account_id:
                continue
            account_key = account_map.get(account_id[0], account_id[1])
            entries_by_account[account_key].append(line)
            totals = account_totals.setdefault(
                account_key,
                {'total_debit': 0.0, 'total_credit': 0.0, 'currency_id': self.env.company.currency_id.symbol, 'account_id': account_id[0]}
            )
            totals['total_debit'] += line.get('debit') or 0.0
            totals['total_credit'] += line.get('credit') or 0.0

        for account_key, lines in entries_by_account.items():
            account_dict[account_key] = lines

        account_dict['account_totals'] = account_totals
        return account_dict

    @api.model
    def get_xlsx_report(self, data, response, report_name, report_action):
        """
        Generate an XLSX report based on the provided data and write it to the
        response stream.

        :param data: The data used to generate the report.
        :type data: str (JSON format)

        :param response: The response object to write the generated report to.
        :type response: werkzeug.wrappers.Response

        :param report_name: The name of the report.
        :type report_name: str
        """
        data = json.loads(data or '{}')
        report_data = data.get('data') or {}
        report_accounts = data.get('account') or [
            key for key in report_data.keys() if key not in ('account_totals', 'journal_ids', 'analytic_ids')
        ]
        report_totals = data.get('total') or report_data.get('account_totals') or {}
        grand_total = data.get('grand_total') or {
            'total_debit': 0.0,
            'total_credit': 0.0,
        }
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        filters = data.get('filters') or {}
        start_date = filters.get('start_date') or ''
        end_date = filters.get('end_date') or ''
        sheet = workbook.add_worksheet()
        head = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '15px'})
        sub_heading = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '10px',
             'border': 1, 'bg_color': '#D3D3D3',
             'border_color': 'black'})
        filter_head = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '10px',
             'border': 1, 'bg_color': '#D3D3D3',
             'border_color': 'black'})
        filter_body = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '10px'})
        side_heading_sub = workbook.add_format(
            {'align': 'left', 'bold': True, 'font_size': '10px',
             'border': 1,
             'border_color': 'black'})
        side_heading_sub.set_indent(1)
        txt_name = workbook.add_format({'font_size': '10px', 'border': 1})
        txt_name.set_indent(2)
        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 1, 20)
        sheet.set_column(2, 2, 15)
        sheet.set_column(3, 3, 15)
        col = 0
        sheet.write('A1:b1', report_name, head)
        sheet.write('B3:b4', 'Date Range', filter_head)
        sheet.write('B4:b4', 'Journals', filter_head)
        sheet.write('B5:b4', 'Analytic', filter_head)
        sheet.write('B6:b4', 'Options', filter_head)
        if start_date or end_date:
            sheet.merge_range('C3:G3', f"{start_date} to {end_date}",
                              filter_body)
        if filters.get('journal'):
            display_names = [journal for journal in filters.get('journal', [])]
            display_names_str = ', '.join(display_names)
            sheet.merge_range('C4:G4', display_names_str, filter_body)
        if filters.get('analytic'):
            display_names = [analytic for analytic in filters.get('analytic', [])]
            account_keys_str = ', '.join(display_names)
            sheet.merge_range('C5:G5', account_keys_str, filter_body)
        if filters.get('options'):
            option_keys = list(filters['options'].keys())
            option_keys_str = ', '.join(option_keys)
            sheet.merge_range('C6:G6', option_keys_str, filter_body)
        if report_accounts:
            if report_action == 'dynamic_accounts_report.action_general_ledger':
                sheet.write(8, col, ' ', sub_heading)
                sheet.write(8, col + 1, 'Date', sub_heading)
                sheet.merge_range('C9:E9', 'Communication', sub_heading)
                sheet.merge_range('F9:G9', 'Partner', sub_heading)
                sheet.merge_range('H9:I9', 'Debit', sub_heading)
                sheet.merge_range('J9:K9', 'Credit', sub_heading)
                sheet.merge_range('L9:M9', 'Balance', sub_heading)
                row = 8
                for account in report_accounts:
                    row += 1
                    account_total = report_totals.get(account, {'total_debit': 0.0, 'total_credit': 0.0})
                    sheet.write(row, col, account, txt_name)
                    sheet.write(row, col + 1, ' ', txt_name)
                    sheet.merge_range(row, col + 2, row, col + 4, ' ', txt_name)
                    sheet.merge_range(row, col + 5, row, col + 6, ' ', txt_name)
                    sheet.merge_range(row, col + 7, row, col + 8,
                                      account_total.get('total_debit', 0.0), txt_name)
                    sheet.merge_range(row, col + 9, row, col + 10,
                                      account_total.get('total_credit', 0.0), txt_name)
                    sheet.merge_range(row, col + 11, row, col + 12,
                                      account_total.get('total_debit', 0.0) - account_total.get('total_credit', 0.0), txt_name)
                    for rec in report_data.get(account, []):
                        row += 1
                        record = rec[0] if isinstance(rec, list) else rec
                        partner = record.get('partner_id')
                        name = partner[1] if isinstance(partner, (list, tuple)) and len(partner) > 1 else None
                        sheet.write(row, col, record.get('move_name', ''), txt_name)
                        sheet.write(row, col + 1, record.get('date', ''), txt_name)
                        sheet.merge_range(row, col + 2, row, col + 4, record.get('name', ''), txt_name)
                        sheet.merge_range(row, col + 5, row, col + 6, name, txt_name)
                        sheet.merge_range(row, col + 7, row, col + 8, record.get('debit', 0.0), txt_name)
                        sheet.merge_range(row, col + 9, row, col + 10, record.get('credit', 0.0), txt_name)
                        sheet.merge_range(row, col + 11, row, col + 12, ' ', txt_name)
                row += 1
                sheet.merge_range(row, col, row, col + 6, 'Total', filter_head)
                sheet.merge_range(row, col + 7, row, col + 8, grand_total.get('total_debit', 0.0), filter_head)
                sheet.merge_range(row, col + 9, row, col + 10, grand_total.get('total_credit', 0.0), filter_head)
                sheet.merge_range(row, col + 11, row, col + 12,
                                  float(grand_total.get('total_debit', 0.0)) - float(grand_total.get('total_credit', 0.0)),
                                  filter_head)
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
