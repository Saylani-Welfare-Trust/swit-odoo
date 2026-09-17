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
            account_map = {account.id: f"{account.code} {account.name}" for account in self.env['account.account'].browse(list(account_ids))}

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
                account.id: f"{account.code} {account.name}"
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
        split_account_ids = set()
        if move_ids:
            all_move_lines = self.env['account.move.line'].search_read(
                [('move_id', 'in', list(move_ids))], ['move_id', 'account_id'])
            for l in all_move_lines:
                if l.get('account_id'):
                    move_account_map[l['move_id'][0]].add(l['account_id'][0])
                    split_account_ids.add(l['account_id'][0])

        split_account_map = {}
        if split_account_ids:
            split_account_map = {
                account.id: f"{account.code} {account.name}"
                for account in self.env['account.account'].browse(list(split_account_ids)).exists()
            }

        def split_account_for(line):
            if not line.get('move_id') or not line.get('account_id'):
                return ''
            others = move_account_map[line['move_id'][0]] - {line['account_id'][0]}
            if not others:
                return ''
            names = sorted(
                split_account_map.get(acc_id, '') for acc_id in others
            )
            return ', '.join(n for n in names if n)

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
        widths = [6, 25, 30, 50, 12, 14, 18, 14, 22, 34, 14, 14, 16]
        last_col = len(headers) - 1

        for idx, w in enumerate(widths):
            sheet.set_column(idx, idx, w)
        sheet.set_default_row(20)

        # ==================== Neutral / clean format palette ====================
        # Company name (larger, bold, dark text)
        company_fmt = workbook.add_format({
            'bold': True, 'font_size': 16, 'font_color': '#1A1A1A',
            'align': 'left', 'valign': 'vcenter'})

        # Report title (medium, bold)
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 13, 'font_color': '#333333',
            'align': 'left', 'valign': 'vcenter'})

        # Date range / subtitle (small gray)
        subtitle_fmt = workbook.add_format({
            'font_size': 10, 'font_color': '#666666',
            'align': 'left', 'valign': 'vcenter'})

        # Printed date (right aligned)
        printed_date_fmt = workbook.add_format({
            'bold': True, 'font_size': 9, 'font_color': '#666666',
            'align': 'right', 'valign': 'vcenter'})

        # Section header (dark bar, white text)
        section_header_fmt = workbook.add_format({
            'bg_color': '#333333', 'font_color': '#FFFFFF',
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'font_size': 10, 'border': 1, 'border_color': '#333333'})

        # Account banner (light gray, bold black text)
        banner_fmt = workbook.add_format({
            'bg_color': '#E8E8E8', 'font_color': '#1A1A1A',
            'bold': True, 'font_size': 10, 'border': 1,
            'border_color': '#BFBFBF', 'align': 'left', 'valign': 'vcenter'})
        banner_fmt.set_indent(1)

        # Opening balance row (very light gray)
        opening_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'bg_color': '#F2F2F2',
            'font_color': '#1A1A1A', 'border': 1, 'border_color': '#BFBFBF',
            'valign': 'vcenter'})
        opening_num_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'bg_color': '#F2F2F2',
            'font_color': '#1A1A1A', 'border': 1, 'border_color': '#BFBFBF',
            'num_format': '#,##0.00', 'valign': 'vcenter'})

        # Transaction line (white, thin gray borders)
        line_fmt = workbook.add_format({
            'font_size': 10, 'border': 1, 'border_color': '#D9D9D9',
            'valign': 'vcenter'})
        name_fmt = workbook.add_format({
            'font_size': 10, 'border': 1, 'border_color': '#D9D9D9',
            'text_wrap': True, 'valign': 'vcenter'})
        num_fmt = workbook.add_format({
            'font_size': 10, 'border': 1, 'border_color': '#D9D9D9',
            'num_format': '#,##0.00', 'valign': 'vcenter'})

        # Per-account total (light gray, bold, top border emphasis)
        total_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'bg_color': '#E8E8E8',
            'font_color': '#1A1A1A', 'border': 1, 'border_color': '#BFBFBF',
            'top': 2, 'top_color': '#333333', 'valign': 'vcenter'})
        total_num_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'bg_color': '#E8E8E8',
            'font_color': '#1A1A1A', 'border': 1, 'border_color': '#BFBFBF',
            'top': 2, 'top_color': '#333333',
            'num_format': '#,##0.00', 'valign': 'vcenter'})

        # Grand total (darker gray, bold, double top border)
        grand_total_fmt = workbook.add_format({
            'bold': True, 'font_size': 11, 'bg_color': '#D9D9D9',
            'font_color': '#1A1A1A', 'border': 1, 'border_color': '#808080',
            'top': 5, 'top_color': '#333333', 'valign': 'vcenter'})
        grand_total_num_fmt = workbook.add_format({
            'bold': True, 'font_size': 11, 'bg_color': '#D9D9D9',
            'font_color': '#1A1A1A', 'border': 1, 'border_color': '#808080',
            'top': 5, 'top_color': '#333333',
            'num_format': '#,##0.00', 'valign': 'vcenter'})

        # --- company / report header block ---
        sheet.set_row(0, 24)
        sheet.set_row(1, 22)
        sheet.set_row(2, 16)
        sheet.merge_range(0, 0, 0, 3, company_name, company_fmt)
        sheet.merge_range(0, 4, 0, last_col, printed_date, printed_date_fmt)
        sheet.merge_range(1, 0, 1, last_col, report_name, title_fmt)
        date_range_text = f"{start_date}  -  {end_date}" if (start_date or end_date) else ''
        sheet.merge_range(2, 0, 2, last_col, date_range_text, subtitle_fmt)

        # Bottom border under the header block
        underline_fmt = workbook.add_format({'bottom': 1, 'bottom_color': '#333333'})
        sheet.merge_range(3, 0, 3, last_col, '', underline_fmt)
        sheet.set_row(3, 4)

        row = 5
        if report_accounts:
            if report_action == 'dynamic_accounts_report.action_general_ledger':
                for account in report_accounts:
                    account_total = report_totals.get(account, {})
                    account_label = account if account != 'false' else 'Unknown Account'

                    # Column headers, repeated per account section
                    for idx, header in enumerate(headers):
                        sheet.write(row, idx, header, section_header_fmt)
                    sheet.set_row(row, 22)
                    row += 1

                    # Account banner
                    sheet.merge_range(row, 0, row, last_col, account_label, banner_fmt)
                    sheet.set_row(row, 22)
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
                        sheet.write(row, 1, account_label.replace(' ', '\n', 1), name_fmt)
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
                        sheet.set_row(row, 30)
                        row += 1

                    # Per-account totals
                    sheet.merge_range(row, 0, row, 9, 'Total', total_fmt)
                    sheet.write(row, 10, account_total.get('total_debit', 0.0), total_num_fmt)
                    sheet.write(row, 11, account_total.get('total_credit', 0.0), total_num_fmt)
                    closing = (account_total.get('opening_balance', 0.0)
                            + account_total.get('total_debit', 0.0)
                            - account_total.get('total_credit', 0.0))
                    sheet.write(row, 12, closing, total_num_fmt)
                    sheet.set_row(row, 24)
                    row += 2  # blank spacer row between account blocks

                # Grand total row
                grand_opening = sum(v.get('opening_balance', 0.0) for v in report_totals.values())
                sheet.merge_range(row, 0, row, 9, 'GRAND TOTAL', grand_total_fmt)
                sheet.write(row, 10, grand_total.get('total_debit', 0.0), grand_total_num_fmt)
                sheet.write(row, 11, grand_total.get('total_credit', 0.0), grand_total_num_fmt)
                sheet.write(row, 12,
                            grand_opening + float(grand_total.get('total_debit', 0.0)) - float(grand_total.get('total_credit', 0.0)),
                            grand_total_num_fmt)
                sheet.set_row(row, 26)

        # Freeze the header rows so they stay visible while scrolling
        sheet.freeze_panes(5, 0)

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()