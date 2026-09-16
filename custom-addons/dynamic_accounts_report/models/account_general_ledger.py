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
             'partner_id', 'account_id']
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
                        method, include_filter_values=True):
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
            domain += [('analytic_line_ids.account_id', 'in', analytic)]

        start_date = end_date = None
        if date_range:
            if date_range == 'month':
                start_date, end_date = today.replace(day=1), today
            elif date_range == 'year':
                start_date, end_date = today.replace(month=1, day=1), today
            elif date_range == 'quarter':
                start_date, end_date = quarter_start, quarter_end
            elif date_range == 'last-month':
                last_month_start = today.replace(day=1) - relativedelta(months=1)
                last_month_end = last_month_start + relativedelta(
                    day=calendar.monthrange(last_month_start.year, last_month_start.month)[1])
                start_date, end_date = last_month_start, last_month_end
            elif date_range == 'last-year':
                last_year_start = today.replace(month=1, day=1) - relativedelta(years=1)
                start_date, end_date = last_year_start, last_year_start.replace(month=12, day=31)
            elif date_range == 'last-quarter':
                start_date, end_date = previous_quarter_start, previous_quarter_end
            elif isinstance(date_range, dict):
                if date_range.get('start_date'):
                    start_date = datetime.strptime(date_range['start_date'], '%Y-%m-%d').date()
                if date_range.get('end_date'):
                    end_date = datetime.strptime(date_range['end_date'], '%Y-%m-%d').date()

            if start_date:
                domain += [('date', '>=', start_date)]
            if end_date:
                domain += [('date', '<=', end_date)]

        move_lines = self.env['account.move.line'].search_read(
            domain,
            ['date', 'name', 'move_id', 'move_name', 'debit', 'credit',
            'partner_id', 'account_id', 'ref', 'journal_id',
            'analytic_distribution']
        )

        if include_filter_values:
            account_dict['journal_ids'] = self.env['account.journal'].search_read([], ['name'])
            account_dict['analytic_ids'] = self.env['account.analytic.account'].search_read([], ['name'])

        account_ids = {line['account_id'][0] for line in move_lines if line.get('account_id')}
        account_map = {}
        if account_ids:
            account_map = {
                account.id: account.display_name
                for account in self.env['account.account'].browse(list(account_ids)).exists()
            }

        # --- opening balance (same domain, minus date filters, dated before start_date) ---
        opening_balances = {}
        if start_date and account_ids:
            opening_domain = [d for d in domain if d[0] != 'date']
            opening_domain += [('date', '<', start_date),
                            ('account_id', 'in', list(account_ids))]
            opening_lines = self.env['account.move.line'].read_group(
                opening_domain, ['debit:sum', 'credit:sum'], ['account_id'])
            for row in opening_lines:
                acc_id = row['account_id'][0]
                opening_balances[acc_id] = (row.get('debit', 0.0) or 0.0) - (row.get('credit', 0.0) or 0.0)

        # --- corresponding/"split" account per move (siblings in the same entry) ---
        move_ids = {line['move_id'][0] for line in move_lines if line.get('move_id')}
        move_account_map = defaultdict(set)
        if move_ids:
            all_move_lines = self.env['account.move.line'].search_read(
                [('move_id', 'in', list(move_ids))], ['move_id', 'account_id'])
            for l in all_move_lines:
                if l.get('account_id'):
                    move_account_map[l['move_id'][0]].add(l['account_id'][1])

        def split_account_for(line):
            if not line.get('move_id') or not line.get('account_id'):
                return ''
            others = move_account_map[line['move_id'][0]] - {line['account_id'][1]}
            if not others:
                return ''
            return list(others)[0] if len(others) == 1 else 'Multiple'

        # --- location from first analytic account on the distribution ---
        analytic_ids = set()
        for line in move_lines:
            dist = line.get('analytic_distribution') or {}
            for k in dist.keys():
                try:
                    analytic_ids.add(int(k))
                except (TypeError, ValueError):
                    pass
        analytic_map = {}
        if analytic_ids:
            analytic_map = {
                a.id: a.display_name
                for a in self.env['account.analytic.account'].browse(list(analytic_ids)).exists()
            }

        def location_for(line):
            dist = line.get('analytic_distribution') or {}
            for k in dist.keys():
                try:
                    k_int = int(k)
                except (TypeError, ValueError):
                    continue
                if k_int in analytic_map:
                    return analytic_map[k_int]
            return ''

        entries_by_account = defaultdict(list)
        for line in sorted(move_lines, key=lambda l: (l.get('date') or '', l.get('id', 0))):
            account_id = line.get('account_id')
            if not account_id:
                continue
            account_key = account_map.get(account_id[0], account_id[1])
            line['split_account'] = split_account_for(line)
            line['location'] = location_for(line)
            line['trx_type'] = line['journal_id'][1] if line.get('journal_id') else ''
            entries_by_account[account_key].append(line)
            totals = account_totals.setdefault(
                account_key,
                {'total_debit': 0.0, 'total_credit': 0.0,
                'currency_id': self.env.company.currency_id.symbol,
                'account_id': account_id[0],
                'opening_balance': opening_balances.get(account_id[0], 0.0)}
            )
            totals['total_debit'] += line.get('debit') or 0.0
            totals['total_credit'] += line.get('credit') or 0.0

        # running balance per account
        for account_key, lines in entries_by_account.items():
            running = account_totals[account_key]['opening_balance']
            for line in lines:
                running += (line.get('debit') or 0.0) - (line.get('credit') or 0.0)
                line['running_balance'] = running
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
        company_name = self.env.company.name
        printed_date = datetime.now().strftime('%d-%b-%y')

        headers = ['Sr', 'Account Name', 'Split Account', 'Location', 'Date',
                   'Trx Type', 'V.No', 'Ref No.', 'Name', 'Description',
                   'Debit', 'Credit', 'Balance']
        widths = [6, 22, 18, 16, 12, 12, 14, 12, 16, 32, 12, 12, 14]
        last_col = len(headers) - 1

        # base red background applied to every cell in the used columns by
        # default; specific rows/cells below override it with their own format
        red_base_fmt = workbook.add_format({'bg_color': '#FF0000'})
        for idx, w in enumerate(widths):
            sheet.set_column(idx, idx, w, red_base_fmt)

        white_company_fmt = workbook.add_format(
            {'bg_color': 'white', 'bold': True, 'font_size': 16,
             'align': 'left', 'valign': 'vcenter'})
        white_title_fmt = workbook.add_format(
            {'bg_color': 'white', 'bold': True, 'font_size': 13,
             'align': 'left', 'valign': 'vcenter'})
        white_sub_fmt = workbook.add_format(
            {'bg_color': 'white', 'font_size': 10,
             'align': 'left', 'valign': 'vcenter'})
        printed_date_fmt = workbook.add_format(
            {'bg_color': 'white', 'bold': True, 'font_size': 9,
             'align': 'right', 'valign': 'vcenter'})
        range_label_fmt = workbook.add_format(
            {'bg_color': '#FFFF00', 'font_color': 'black', 'bold': True,
             'font_size': 10, 'align': 'left', 'border': 1})
        range_label_fmt.set_indent(1)
        range_value_fmt = workbook.add_format(
            {'bg_color': '#FF0000', 'font_color': 'white', 'bold': True,
             'font_size': 10, 'align': 'left', 'border': 1})
        range_value_fmt.set_indent(1)
        section_header_fmt = workbook.add_format(
            {'bg_color': '#FF0000', 'font_color': '#FFFF00', 'bold': True,
             'align': 'center', 'font_size': 10, 'border': 1})
        banner_fmt = workbook.add_format(
            {'bg_color': '#C0C0C0', 'font_color': 'black', 'bold': True,
             'font_size': 10, 'border': 1, 'align': 'left'})
        banner_fmt.set_indent(1)
        opening_fmt = workbook.add_format(
            {'bold': True, 'font_size': '10px', 'border': 1,
             'bg_color': '#FF0000', 'font_color': 'white'})
        opening_num_fmt = workbook.add_format(
            {'bold': True, 'font_size': '10px', 'border': 1,
             'bg_color': '#FF0000', 'font_color': 'white',
             'num_format': '#,##0.00'})
        line_fmt = workbook.add_format(
            {'font_size': '10px', 'border': 1, 'bg_color': '#FF0000'})
        num_fmt = workbook.add_format(
            {'font_size': '10px', 'border': 1, 'bg_color': '#FF0000',
             'num_format': '#,##0.00'})
        total_fmt = workbook.add_format(
            {'bold': True, 'font_size': '10px', 'border': 1,
             'bg_color': '#FFFF00'})
        total_num_fmt = workbook.add_format(
            {'bold': True, 'font_size': '10px', 'border': 1,
             'bg_color': '#FFFF00', 'num_format': '#,##0.00'})

        # --- company / report header block ---
        sheet.merge_range(0, 0, 0, 3, company_name, white_company_fmt)
        sheet.merge_range(0, 4, 0, last_col, printed_date, printed_date_fmt)
        sheet.merge_range(1, 0, 1, last_col, report_name, white_title_fmt)
        date_range_text = f"{start_date} - {end_date}" if (start_date or end_date) else ''
        sheet.merge_range(2, 0, 2, last_col, date_range_text, white_sub_fmt)

        # --- account from / account to range ---
        sorted_accounts = sorted(a for a in report_accounts if a and a != 'false')
        account_from = sorted_accounts[0] if sorted_accounts else ''
        account_to = sorted_accounts[-1] if sorted_accounts else ''
        sheet.write(4, 1, 'Account From :', range_label_fmt)
        sheet.merge_range(4, 2, 4, 6, account_from, range_value_fmt)
        sheet.write(5, 1, 'Account To :', range_label_fmt)
        sheet.merge_range(5, 2, 5, 6, account_to, range_value_fmt)

        row = 8
        if report_accounts:
            if report_action == 'dynamic_accounts_report.action_general_ledger':
                for account in report_accounts:
                    account_total = report_totals.get(account, {})
                    account_label = account if account != 'false' else 'Unknown Account'

                    # Column headers, repeated for every account section
                    for idx, header in enumerate(headers):
                        sheet.write(row, idx, header, section_header_fmt)
                    row += 1

                    # Account banner
                    sheet.merge_range(row, 0, row, last_col, account_label, banner_fmt)
                    row += 1

                    # Opening balance
                    sheet.write(row, 0, '00', opening_fmt)
                    sheet.merge_range(row, 1, row, 9, 'OPENING BALANCE', opening_fmt)
                    sheet.write(row, 10, '', opening_fmt)
                    sheet.write(row, 11, '', opening_fmt)
                    sheet.write(row, 12, account_total.get('opening_balance', 0.0), opening_num_fmt)
                    row += 1

                    # Transaction lines
                    for sr, rec in enumerate(report_data.get(account, []), start=1):
                        record = rec[0] if isinstance(rec, list) else rec
                        partner = record.get('partner_id')
                        partner_name = partner[1] if isinstance(partner, (list, tuple)) and len(partner) > 1 else ''
                        sheet.write(row, 0, sr, line_fmt)
                        sheet.write(row, 1, account_label, line_fmt)
                        sheet.write(row, 2, record.get('split_account', ''), line_fmt)
                        sheet.write(row, 3, record.get('location', ''), line_fmt)
                        sheet.write(row, 4, record.get('date', ''), line_fmt)
                        sheet.write(row, 5, record.get('trx_type', ''), line_fmt)
                        sheet.write(row, 6, record.get('move_name', ''), line_fmt)
                        sheet.write(row, 7, record.get('ref', ''), line_fmt)
                        sheet.write(row, 8, partner_name, line_fmt)
                        sheet.write(row, 9, record.get('name', ''), line_fmt)
                        sheet.write(row, 10, record.get('debit', 0.0) or '', num_fmt)
                        sheet.write(row, 11, record.get('credit', 0.0) or '', num_fmt)
                        sheet.write(row, 12, record.get('running_balance', 0.0), num_fmt)
                        row += 1

                    # Per-account totals
                    sheet.merge_range(row, 0, row, 9, 'Total', total_fmt)
                    sheet.write(row, 10, account_total.get('total_debit', 0.0), total_num_fmt)
                    sheet.write(row, 11, account_total.get('total_credit', 0.0), total_num_fmt)
                    closing = (account_total.get('opening_balance', 0.0)
                            + account_total.get('total_debit', 0.0)
                            - account_total.get('total_credit', 0.0))
                    sheet.write(row, 12, closing, total_num_fmt)
                    row += 2  # blank row between account blocks

                # Grand total row
                grand_opening = sum(v.get('opening_balance', 0.0) for v in report_totals.values())
                sheet.merge_range(row, 0, row, 9, 'Grand Total', total_fmt)
                sheet.write(row, 10, grand_total.get('total_debit', 0.0), total_num_fmt)
                sheet.write(row, 11, grand_total.get('total_credit', 0.0), total_num_fmt)
                sheet.write(row, 12,
                            grand_opening + float(grand_total.get('total_debit', 0.0)) - float(grand_total.get('total_credit', 0.0)),
                            total_num_fmt)
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
