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
import calendar
import io
import json
from collections import defaultdict
from datetime import datetime
import xlsxwriter
from odoo import api, fields, models
from odoo.tools.date_utils import get_month, get_fiscal_year, \
    get_quarter_number, subtract

# Mirrors Odoo's native two-level Chart of Accounts grouping:
#   Internal Group  (Asset / Liability / Equity / Income / Expense)
#     └── Account Type  (Bank and Cash, Current Assets, Receivable, ...)
# internal_group_order matches Odoo's own alphabetical default
# (Asset, Equity, Expense, Income, Liability); group_order matches the
# sub-type order seen in Odoo's own Chart of Accounts list.
ACCOUNT_TYPE_GROUPS = {
    'asset_cash':             ('Asset', 1, 'Bank and Cash', 1),
    'asset_current':          ('Asset', 1, 'Current Assets', 2),
    'asset_non_current':      ('Asset', 1, 'Non-current Assets', 3),
    'asset_receivable':       ('Asset', 1, 'Receivable', 4),
    'asset_prepayments':      ('Asset', 1, 'Prepayments', 5),
    'asset_fixed':            ('Asset', 1, 'Fixed Assets', 6),

    'equity':                 ('Equity', 2, 'Equity', 1),
    'equity_unaffected':      ('Equity', 2, 'Current Year Earnings', 2),

    'expense':                ('Expense', 3, 'Expenses', 1),
    'expense_direct_cost':    ('Expense', 3, 'Cost of Revenue', 2),
    'expense_depreciation':   ('Expense', 3, 'Depreciation', 3),

    'income':                 ('Income', 4, 'Income', 1),
    'income_other':           ('Income', 4, 'Other Income', 2),

    'liability_current':      ('Liability', 5, 'Current Liabilities', 1),
    'liability_non_current':  ('Liability', 5, 'Non-current Liabilities', 2),
    'liability_payable':      ('Liability', 5, 'Payable', 3),
    'liability_credit_card':  ('Liability', 5, 'Credit Card', 4),

    'off_balance':            ('Off Balance', 6, 'Off-Balance Sheet', 1),
}


def _group_info(account_type):
    """Returns (internal_group, internal_group_order, group_label, group_order)."""
    return ACCOUNT_TYPE_GROUPS.get(account_type, ('Other', 99, 'Other', 99))

class AccountTrialBalance(models.TransientModel):
    """For creating Trial Balance report"""
    _name = 'account.trial.balance'
    _description = 'Trial Balance Report'

    
    
    @api.model
    def view_report(self):
        today = fields.Date.today()
        first_day, last_day = get_month(today)

        move_lines = self.env['account.move.line'].search_read(
            [('parent_state', '=', 'posted')],
            ['date', 'account_id', 'debit', 'credit']
        )

        account_totals = defaultdict(lambda: {'initial_total_debit': 0.0, 'initial_total_credit': 0.0, 'total_debit': 0.0, 'total_credit': 0.0})
        account_records = {}

        for line in move_lines:
            account_id = line.get('account_id')
            if not account_id:
                continue
            account_id = account_id[0]
            if account_id not in account_records:
                account_records[account_id] = self.env['account.account'].browse(account_id)
            if line.get('date') and line['date'] < first_day:
                account_totals[account_id]['initial_total_debit'] += line.get('debit') or 0.0
                account_totals[account_id]['initial_total_credit'] += line.get('credit') or 0.0
            elif line.get('date') and first_day <= line['date'] <= last_day:
                account_totals[account_id]['total_debit'] += line.get('debit') or 0.0
                account_totals[account_id]['total_credit'] += line.get('credit') or 0.0

        move_line_list = []
        for account_id, values in account_totals.items():
            account = account_records[account_id]
            initial_total_debit = round(values['initial_total_debit'], 2)
            initial_total_credit = round(values['initial_total_credit'], 2)
            total_debit = round(values['total_debit'], 2)
            total_credit = round(values['total_credit'], 2)
            sum_debit = initial_total_debit + total_debit
            sum_credit = initial_total_credit + total_credit
            diff_credit_debit = sum_debit - sum_credit
            if diff_credit_debit > 0:
                end_total_debit = diff_credit_debit
                end_total_credit = 0.0
            else:
                end_total_debit = 0.0
                end_total_credit = abs(diff_credit_debit)

            internal_group, internal_group_order, group_label, group_order = _group_info(account.account_type)

            move_line_list.append({
                'account': account.display_name,
                'account_name': account.name,
                'account_id': account_id,
                'account_code': account.code or '',
                'internal_group': internal_group,
                'internal_group_order': internal_group_order,
                'group_label': group_label,
                'group_order': group_order,
                'journal_ids': self.env['account.journal'].search_read([], ['name']),
                'initial_total_debit': initial_total_debit,
                'initial_total_credit': initial_total_credit,
                'initial_balance': initial_total_debit - initial_total_credit,
                'total_debit': total_debit,
                'total_credit': total_credit,
                'end_total_debit': end_total_debit,
                'end_total_credit': end_total_credit,
                # Net closing figure: positive = net debit balance, negative = net credit balance.
                'end_balance': end_total_debit - end_total_credit,
            })

        move_line_list.sort(key=lambda d: (d['internal_group_order'], d['group_order'], d['account_code']))
        return move_line_list

    @api.model
    def get_filter_values(self, start_date, end_date, comparison_number,
                          comparison_type, journal_list, analytic, options,
                          method):
        """
        Retrieves and calculates filtered values for generating a financial
        report.
        Retrieves and processes account movement data based on the provided
        filters. Calculates initial, dynamic, and end total debit and credit
        amounts for each account,considering date range, comparison type, and
        other filter criteria.

        :param str start_date: Start date of the reporting period.
        :param str end_date: End date of the reporting period.
        :param int comparison_number: Number of periods for comparison.
        :param str comparison_type: Type of comparison (month, year, quarter).
        :param list[int] journal_list: List of selected journal IDs.
        :param list[int] analytic: List of selected analytic line IDs.
        :param dict options: Additional filtering options (e.g., 'draft').
        :param dict method: Find the method.
        :return: List of dictionaries representing the financial report.
        :rtype: list
        """
        
        if not start_date or not end_date:
            return []
        if options == {}:
            options = None
        if options is None:
            option_domain = ['posted']
        elif 'draft' in options:
            option_domain = ['posted', 'draft']
        if method == {}:
            method = None
        dynamic_total_debit = {}
        dynamic_date_num = {}
        dynamic_total_credit = {}
                # `analytic` here actually carries selected account.account ids from
        # the "Account" filter (placeholder is 'Account', not an analytic
        # account). When specific accounts are picked, show only those;
        # otherwise show every account. Either way, sort by code.
        if analytic:
            account_ids = self.env['account.account'].browse(analytic).exists()
        else:
            account_ids = self.env['account.move.line'].search([]).mapped(
                'account_id')
        account_ids = account_ids.sorted(key=lambda a: a.code or '')
        move_line_list = []
        start_date_first = \
            get_fiscal_year(datetime.strptime(start_date, "%Y-%m-%d").date())[
                0] if comparison_type == 'year' else datetime.strptime(
                start_date, "%Y-%m-%d").date()
        end_date_first = \
            get_fiscal_year(datetime.strptime(end_date, "%Y-%m-%d").date())[
                1] if comparison_type == 'year' else datetime.strptime(end_date,
                                                                       "%Y-%m-%d").date()
        for account_id in account_ids:
            start_date = start_date_first
            end_date = end_date_first
            if comparison_number:
                if comparison_type == 'month':
                    initial_start_date = subtract(start_date, months=eval(
                        comparison_number))
                elif comparison_type == 'year':
                    initial_start_date = subtract(start_date, years=eval(
                        comparison_number))
                else:
                    initial_start_date = subtract(start_date, months=eval(
                        comparison_number) * 3)
            else:
                initial_start_date = start_date
            domain = [('date', '<', initial_start_date),
                      ('account_id', '=', account_id.id),
                      ('parent_state', 'in', option_domain), ]
            if journal_list:
                domain.append(
                    ('journal_id', 'in', journal_list), )
            # if analytic:
            #     domain.append(
            #         ('analytic_line_ids', 'in', analytic))
            if method is not None and 'cash' in method:
                domain.append(('journal_id', 'in',
                               self.env.company.tax_cash_basis_journal_id.ids))
            initial_move_line_ids = self.env['account.move.line'].search(
                domain)
            initial_total_debit = round(
                sum(initial_move_line_ids.mapped('debit')), 2)
            initial_total_credit = round(
                sum(initial_move_line_ids.mapped('credit')), 2)
            if comparison_number:
                if comparison_type == 'year':
                    for i in range(1, eval(comparison_number) + 1):
                        com_start_date = subtract(start_date, years=i)
                        com_end_date = subtract(end_date, years=i)
                        domain = [('date', '>=', com_start_date),
                                  ('account_id', '=', account_id.id),
                                  ('date', '<=', com_end_date),
                                  ('parent_state', 'in', option_domain), ]
                        if journal_list:
                            domain.append(
                                ('journal_id', 'in', journal_list), )
                        # if analytic:
                        #     domain.append(
                        #         ('analytic_line_ids', 'in', analytic))
                        if method is not None and 'cash' in method:
                            domain.append(('journal_id', 'in',
                                           self.env.company.tax_cash_basis_journal_id.ids))
                        move_lines = self.env['account.move.line'].search(
                            domain)
                        dynamic_total_debit[
                            f"dynamic_total_debit_{i}"] = round(
                            sum(move_lines.mapped('debit')), 2)
                        dynamic_total_credit[
                            f"dynamic_total_credit_{i}"] = round(
                            sum(move_lines.mapped('credit')), 2)
                if comparison_type == 'month':
                    dynamic_date_num[
                        f"dynamic_date_num{0}"] = self.get_month_name(
                        start_date) + ' ' + str(
                        start_date.year)
                    for i in range(1, eval(comparison_number) + 1):
                        com_start_date = subtract(start_date, months=i)
                        com_end_date = subtract(end_date, months=i)
                        domain = [('date', '>=', com_start_date),
                                  ('account_id', '=', account_id.id),
                                  ('date', '<=', com_end_date),
                                  ('parent_state', 'in', option_domain), ]
                        if journal_list:
                            domain.append(
                                ('journal_id', 'in', journal_list), )
                        # if analytic:
                        #     domain.append(
                        #         ('analytic_line_ids', 'in', analytic))
                        if method is not None and 'cash' in method:
                            domain.append(('journal_id', 'in',
                                           self.env.company.tax_cash_basis_journal_id.ids), )
                        move_lines = self.env['account.move.line'].search(
                            domain)
                        dynamic_date_num[
                            f"dynamic_date_num{i}"] = self.get_month_name(
                            com_start_date) + ' ' + str(
                            com_start_date.year)
                        dynamic_total_debit[
                            f"dynamic_total_debit_{i}"] = round(
                            sum(move_lines.mapped('debit')), 2)
                        dynamic_total_credit[
                            f"dynamic_total_credit_{i}"] = round(
                            sum(move_lines.mapped('credit')), 2)
                if comparison_type == 'quarter':
                    dynamic_date_num[
                        f"dynamic_date_num{0}"] = 'Q' + ' ' + str(
                        get_quarter_number(start_date)) + ' ' + str(
                        start_date.year)
                    for i in range(1, eval(comparison_number) + 1):
                        com_start_date = subtract(start_date, months=i * 3)
                        com_end_date = subtract(end_date, months=i * 3)
                        domain = [('date', '>=', com_start_date),
                                  ('account_id', '=', account_id.id),
                                  ('date', '<=', com_end_date),
                                  ('parent_state', 'in', option_domain), ]
                        if journal_list:
                            domain.append(
                                ('journal_id', 'in', journal_list), )
                        # if analytic:
                        #     domain.append(
                        #         ('analytic_line_ids', 'in', analytic))
                        if method is not None and 'cash' in method:
                            domain.append(('journal_id', 'in',
                                           self.env.company.tax_cash_basis_journal_id.ids))
                        move_lines = self.env['account.move.line'].search(
                            domain)
                        dynamic_date_num[
                            f"dynamic_date_num{i}"] = 'Q' + ' ' + str(
                            get_quarter_number(com_start_date)) + ' ' + str(
                            com_start_date.year)
                        dynamic_total_debit[
                            f"dynamic_total_debit_{i}"] = round(
                            sum(move_lines.mapped('debit')), 2)
                        dynamic_total_credit[
                            f"dynamic_total_credit_{i}"] = round(
                            sum(move_lines.mapped('credit')), 2)
            domain = [('date', '>=', start_date),
                      ('account_id', '=', account_id.id),
                      ('date', '<=', end_date),
                      ('parent_state', 'in', option_domain), ]
            if journal_list:
                domain.append(
                    ('journal_id', 'in', journal_list), )
            # if analytic:
            #     domain.append(
            #         ('analytic_line_ids', 'in', analytic))
            if method is not None and 'cash' in method:
                domain.append(('journal_id', 'in',
                               self.env.company.tax_cash_basis_journal_id.ids))
            move_line_ids = self.env['account.move.line'].search(domain)
            total_debit = round(sum(move_line_ids.mapped('debit')), 2)
            total_credit = round(sum(move_line_ids.mapped('credit')), 2)
            sum_debit = initial_total_debit + sum(
                dynamic_total_debit.values()) + total_debit
            sum_credit = initial_total_credit + sum(
                dynamic_total_credit.values()) + total_credit
            diff_credit_debit = sum_debit - sum_credit
            if diff_credit_debit > 0:
                end_total_debit = diff_credit_debit
                end_total_credit = 0.0
            else:
                end_total_debit = 0.0
                end_total_credit = abs(diff_credit_debit)
            internal_group, internal_group_order, group_label, group_order = _group_info(account_id.account_type)
            data = {
                'account': account_id.display_name,
                'account_name': account_id.name,
                'account_id': account_id.id,
                'account_code': account_id.code or '',
                'internal_group': internal_group,
                'internal_group_order': internal_group_order,
                'group_label': group_label,
                'group_order': group_order,
                'journal_ids': self.env['account.journal'].search_read([], [
                    'name']),
                'initial_total_debit': initial_total_debit,
                'initial_total_credit': initial_total_credit,
                'initial_balance': initial_total_debit - initial_total_credit,
                'total_debit': total_debit,
                'total_credit': total_credit,
                'end_total_debit': end_total_debit,
                'end_total_credit': end_total_credit,
                'end_balance': end_total_debit - end_total_credit,
            }
            if comparison_number:
                if dynamic_date_num:
                    data['dynamic_date_num'] = dynamic_date_num
                for i in range(1, eval(comparison_number) + 1):
                    data[f'dynamic_total_debit_{i}'] = dynamic_total_debit.get(
                        f"dynamic_total_debit_{eval(comparison_number) + 1 - i}",
                        0.0)
                    data[
                        f'dynamic_total_credit_{i}'] = dynamic_total_credit.get(
                        f"dynamic_total_credit_{eval(comparison_number) + 1 - i}",
                        0.0)
            move_line_list.append(data)

        move_line_list.sort(
            key=lambda d: (d['internal_group_order'], d['group_order'], d['account_code'])
        )
        return move_line_list

    @api.model
    def get_month_name(self, date):
        """
        Retrieve the abbreviated name of the month for a given date.
        :param date: The date for which to retrieve the month's abbreviated name.
        :type date: datetime.date
        :return: Abbreviated name of the month (e.g., 'Jan', 'Feb', ..., 'Dec').
        :rtype: str
        """
        month_names = calendar.month_abbr
        return month_names[date.month]

    @api.model
    def get_xlsx_report(self, data, response, report_name, report_action):
        """
        Generate an XLSX report based on provided data and response stream.
        Generates an Excel workbook with specified report format, including
        subheadings, column headers, and row data for the given financial
        report data.
        """
        data = json.loads(data)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        start_date = data['filters']['start_date'] if data['filters']['start_date'] else ''
        end_date = data['filters']['end_date'] if data['filters']['end_date'] else ''
        sheet = workbook.add_worksheet()

        # ------------------------------------------------------------------
        #  Title + subtitle
        # ------------------------------------------------------------------
        head = workbook.add_format(
            {'font_size': 18, 'align': 'center', 'bold': True,
             'font_color': '#222'})
        subtitle = workbook.add_format(
            {'font_size': 11, 'align': 'center', 'italic': True,
             'font_color': '#555'})

        # ------------------------------------------------------------------
        #  Filter band formats
        # ------------------------------------------------------------------
        filter_head = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10,
             'border': 1, 'bg_color': '#3a3a3a', 'font_color': 'white',
             'border_color': 'black'})
        filter_body = workbook.add_format(
            {'align': 'center', 'font_size': 10, 'border': 1})

        # ------------------------------------------------------------------
        #  Table header formats (dark band with white text)
        # ------------------------------------------------------------------
        sub_heading = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 11,
             'border': 1, 'bg_color': '#3a3a3a', 'font_color': 'white',
             'border_color': 'black', 'text_wrap': True,
             'valign': 'vcenter'})

        # ------------------------------------------------------------------
        #  Row formats
        # ------------------------------------------------------------------
        side_heading_sub = workbook.add_format(
            {'align': 'left', 'font_size': 10, 'border': 1,
             'border_color': '#cccccc'})
        side_heading_sub.set_indent(1)

        txt_name = workbook.add_format(
            {'font_size': 10, 'border': 1, 'border_color': '#cccccc'})
        txt_name.set_indent(2)

        num_fmt_whole = workbook.add_format(
            {'font_size': 10, 'border': 1, 'num_format': '#,##0',
             'border_color': '#cccccc'})

        # ------------------------------------------------------------------
        #  Group hierarchy formats
        # ------------------------------------------------------------------
        internal_header_fmt = workbook.add_format(
            {'bold': True, 'font_size': 14, 'bg_color': '#CFCFCF',
             'border': 1, 'border_color': '#888', 'valign': 'vcenter'})
        internal_header_fmt.set_indent(1)

        group_header_fmt = workbook.add_format(
            {'bold': True, 'font_size': 12, 'bg_color': '#EAEAEA',
             'border': 1, 'border_color': '#aaa', 'valign': 'vcenter'})
        group_header_fmt.set_indent(2)

        group_total_fmt = workbook.add_format(
            {'bold': True, 'font_size': 12, 'border': 1,
             'border_color': '#aaa', 'top': 2, 'num_format': '#,##0',
             'bg_color': '#F4F4F4'})
        group_total_lbl_fmt = workbook.add_format(
            {'bold': True, 'font_size': 12, 'border': 1,
             'border_color': '#aaa', 'top': 2,
             'bg_color': '#F4F4F4', 'align': 'left'})

        internal_total_fmt = workbook.add_format(
            {'bold': True, 'font_size': 13, 'border': 1,
             'border_color': '#888', 'top': 6, 'num_format': '#,##0',
             'bg_color': '#DADADA'})
        internal_total_lbl_fmt = workbook.add_format(
            {'bold': True, 'font_size': 13, 'border': 1,
             'border_color': '#888', 'top': 6,
             'bg_color': '#DADADA', 'align': 'left'})

        grand_fmt = workbook.add_format(
            {'bold': True, 'font_size': 13, 'bg_color': '#3a3a3a',
             'font_color': 'white', 'border': 1, 'border_color': 'black',
             'num_format': '#,##0', 'top': 6})
        grand_lbl_fmt = workbook.add_format(
            {'bold': True, 'font_size': 13, 'bg_color': '#3a3a3a',
             'font_color': 'white', 'border': 1, 'border_color': 'black',
             'top': 6, 'align': 'left'})

        # ------------------------------------------------------------------
        #  Column widths
        # ------------------------------------------------------------------
        sheet.set_column(0, 0, 16)   # Account Number
        sheet.set_column(1, 1, 34)   # Account Name
        sheet.set_column(2, 2, 15)   # Initial Balance (net)
        col = 0

        # ------------------------------------------------------------------
        #  Title
        # ------------------------------------------------------------------
        sheet.merge_range('A1:G1', report_name, head)
        sheet.merge_range('A2:G2', 'Trial Balance Report', subtitle)
        sheet.set_row(0, 30)
        sheet.set_row(1, 18)

        # ------------------------------------------------------------------
        #  Filter band
        # ------------------------------------------------------------------
        sheet.write('B4:B4', 'Date Range', filter_head)
        sheet.write('B5:B4', 'Comparison', filter_head)
        sheet.write('B6:B4', 'Journal', filter_head)
        sheet.write('B7:B4', 'Account', filter_head)
        sheet.write('B8:B4', 'Option', filter_head)

        if start_date or end_date:
            sheet.merge_range('C4:G4', f"{start_date} to {end_date}", filter_body)
        if data['filters']['comparison_number_range']:
            sheet.merge_range(
                'C5:G5',
                f"{data['filters']['comparison_type']} : {data['filters']['comparison_number_range']}",
                filter_body)
        if data['filters']['journal']:
            display_names = [journal for journal in data['filters']['journal']]
            sheet.merge_range('C6:G6', ', '.join(display_names), filter_body)
        if data['filters']['account']:
            account_keys = [account.get('display_name', 'undefined')
                            for account in data['filters']['account']]
            sheet.merge_range('C7:G7', ', '.join(account_keys), filter_body)
        if data['filters']['options']:
            option_keys = list(data['filters']['options'].keys())
            sheet.merge_range('C8:G8', ', '.join(option_keys), filter_body)

        # ------------------------------------------------------------------
        #  Main table header rows
        # ------------------------------------------------------------------
        sheet.write(10, col, 'Account No.', sub_heading)
        sheet.write(10, col + 1, 'Account Name', sub_heading)
        sheet.write(10, col + 2, 'Initial Balance', sub_heading)
        i = 3
        for date_view in data['date_viewed']:
            sheet.merge_range(10, col + i, 10, col + i + 1, date_view, sub_heading)
            i += 2
        sheet.write(10, col + i, 'End Balance', sub_heading)

        sheet.write(11, col, '', sub_heading)
        sheet.write(11, col + 1, '', sub_heading)
        sheet.write(11, col + 2, '', sub_heading)
        i = 3
        for date_views in data['date_viewed']:
            sheet.write(11, col + i, 'Debit', sub_heading)
            i += 1
            sheet.write(11, col + i, 'Credit', sub_heading)
            i += 1
        sheet.write(11, col + i, '', sub_heading)

        sheet.set_row(10, 22)
        sheet.set_row(11, 20)

        # ------------------------------------------------------------------
        #  Data body
        # ------------------------------------------------------------------
        if data and report_action == 'dynamic_accounts_report.action_trial_balance':
            row = 12
            apply_cmp = data['apply_comparison']
            periods = data['comparison_number_range'] if apply_cmp else []
            last_col = col + 5 + (2 * len(data['date_viewed']))

            def _s(rows, key):
                return sum(m.get(key, 0.0) for m in rows)

            def write_internal_header(label):
                nonlocal row
                sheet.merge_range(row, col, row, last_col, label,
                                  internal_header_fmt)
                sheet.set_row(row, 26)
                row += 1

            def write_group_header(label):
                nonlocal row
                sheet.merge_range(row, col, row, last_col, label,
                                  group_header_fmt)
                sheet.set_row(row, 20)
                row += 1

            def write_total(label, rows, fmt_num, fmt_lbl):
                nonlocal row
                sheet.write(row, col, '', fmt_lbl)
                sheet.write(row, col + 1, label, fmt_lbl)
                sheet.write(row, col + 2, _s(rows, 'initial_balance'), fmt_num)
                j = 3
                if apply_cmp:
                    for num in periods:
                        sheet.write(row, col + j,
                                    _s(rows, 'dynamic_total_debit_' + str(num)), fmt_num)
                        sheet.write(row, col + j + 1,
                                    _s(rows, 'dynamic_total_credit_' + str(num)), fmt_num)
                        j += 2
                sheet.write(row, col + j,     _s(rows, 'total_debit'),  fmt_num)
                sheet.write(row, col + j + 1, _s(rows, 'total_credit'), fmt_num)
                sheet.write(row, col + j + 2, _s(rows, 'end_balance'),  fmt_num)
                sheet.set_row(row, 20)
                row += 1

            def write_account(move_line):
                nonlocal row
                sheet.write(row, col, move_line.get('account_code', ''), txt_name)
                sheet.write(row, col + 1,
                            move_line.get('account_name', move_line['account']),
                            side_heading_sub)
                sheet.write(row, col + 2,
                            move_line.get('initial_balance', 0.0), num_fmt_whole)
                j = 3
                if apply_cmp:
                    for num in periods:
                        sheet.write(row, col + j,
                                    move_line.get('dynamic_total_debit_' + str(num), 0.0),
                                    num_fmt_whole)
                        sheet.write(row, col + j + 1,
                                    move_line.get('dynamic_total_credit_' + str(num), 0.0),
                                    num_fmt_whole)
                        j += 2
                sheet.write(row, col + j,     move_line.get('total_debit', 0.0),  num_fmt_whole)
                sheet.write(row, col + j + 1, move_line.get('total_credit', 0.0), num_fmt_whole)
                sheet.write(row, col + j + 2, move_line.get('end_balance', 0.0),  num_fmt_whole)
                row += 1

            current_internal_group = None
            current_group = None
            internal_group_rows = []
            group_rows = []

            for move_line in data['data']:
                ig = move_line.get('internal_group') or 'Other'
                gl = move_line.get('group_label') or 'Other'

                # --- internal group boundary ---
                if ig != current_internal_group:
                    if current_group is not None and group_rows:
                        write_total('Total', group_rows,
                                    group_total_fmt, group_total_lbl_fmt)
                        group_rows = []
                    if current_internal_group is not None and internal_group_rows:
                        write_total(f'{current_internal_group} Total',
                                    internal_group_rows,
                                    internal_total_fmt, internal_total_lbl_fmt)
                        internal_group_rows = []
                    write_internal_header(ig.upper())
                    current_internal_group = ig
                    current_group = None

                # --- sub-group boundary ---
                if gl != current_group:
                    if current_group is not None and group_rows:
                        write_total('Total', group_rows,
                                    group_total_fmt, group_total_lbl_fmt)
                        group_rows = []
                    write_group_header(gl)
                    current_group = gl

                write_account(move_line)
                group_rows.append(move_line)
                internal_group_rows.append(move_line)

            # --- close last sub-group ---
            if current_group is not None and group_rows:
                write_total('Total', group_rows,
                            group_total_fmt, group_total_lbl_fmt)
            # --- close last internal group ---
            if current_internal_group is not None and internal_group_rows:
                write_total(f'{current_internal_group} Total',
                            internal_group_rows,
                            internal_total_fmt, internal_total_lbl_fmt)

            # --- grand total ---
            all_rows = data['data']
            sheet.write(row, col, '', grand_lbl_fmt)
            sheet.write(row, col + 1, 'GRAND TOTAL', grand_lbl_fmt)
            sheet.write(row, col + 2, _s(all_rows, 'initial_balance'), grand_fmt)
            j = 3
            if apply_cmp:
                for num in periods:
                    sheet.write(row, col + j,
                                _s(all_rows, 'dynamic_total_debit_' + str(num)), grand_fmt)
                    sheet.write(row, col + j + 1,
                                _s(all_rows, 'dynamic_total_credit_' + str(num)), grand_fmt)
                    j += 2
            sheet.write(row, col + j,     _s(all_rows, 'total_debit'),  grand_fmt)
            sheet.write(row, col + j + 1, _s(all_rows, 'total_credit'), grand_fmt)
            sheet.write(row, col + j + 2, _s(all_rows, 'end_balance'),  grand_fmt)
            sheet.set_row(row, 24)
            row += 1

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
