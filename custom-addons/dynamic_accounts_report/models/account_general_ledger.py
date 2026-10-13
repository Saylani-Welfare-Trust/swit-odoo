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
from odoo.exceptions import UserError


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
        account_meta = {}
        if account_ids:
            account_records = self.env['account.account'].browse(list(account_ids))
            account_map = {a.id: f"{a.code} {a.name}" for a in account_records}
            account_meta = {a.id: {'code': a.code or '', 'name': a.name or ''} for a in account_records}

        for line in move_lines:
            account_id = line.get('account_id')
            if not account_id:
                continue
            account_key = account_map.get(account_id[0], account_id[1])
            entries_by_account[account_key].append(line)
            totals = account_totals.setdefault(
                account_key,
                {'total_debit': 0.0, 'total_credit': 0.0,
                'currency_id': self.env.company.currency_id.symbol,
                'account_id': account_id[0],
                'account_code': account_meta.get(account_id[0], {}).get('code', ''),
                'account_name': account_meta.get(account_id[0], {}).get('name', account_key)}
            )
            totals['total_debit'] += line.get('debit') or 0.0
            totals['total_credit'] += line.get('credit') or 0.0

        for account_key, lines in entries_by_account.items():
            account_dict[account_key] = lines

        account_dict['account_totals'] = account_totals
        return account_dict

    @api.model
    def get_filter_values(self, journal_id, date_range, options, analytic, method,
                        include_filter_values=True, offset=0, limit=20,
                        search_query=''):
        """
        Paginated GL loader.
        - offset / limit: paginate ACCOUNTS (each page includes those accounts' lines)
        - search_query: server-side search across account name/code + line text
        Returns:
        {
            'account':        [<account keys for this page>],
            'account_totals': { key: {..totals..} },
            'total_accounts': int,
            'has_more':       bool,
            'offset':         int,
            'journal_ids':    [...],   # only when offset == 0
            'analytic_ids':   [...],   # only when offset == 0
        }
        """
        # -------- build domain (same logic as before) --------
        today = fields.Date.today()
        quarter_start, quarter_end = date_utils.get_quarter(today)
        previous_quarter_start = quarter_start - relativedelta(months=3)
        previous_quarter_end = quarter_start - relativedelta(days=1)

        if options == {}:
            options = None
        option_domain = ['posted'] if options is None else (
            ['posted', 'draft'] if 'draft' in options else ['posted'])

        domain = []
        if journal_id:
            domain.append(('journal_id', 'in', journal_id))
        domain.append(('parent_state', 'in', option_domain))

        if method and 'cash' in method:
            domain.append(('journal_id', 'in',
                        self.env.company.tax_cash_basis_journal_id.ids))
        if analytic:
            domain.append(('analytic_line_ids.account_id', 'in', analytic))

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
                    day=calendar.monthrange(last_month_start.year,
                                            last_month_start.month)[1])
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
                domain.append(('date', '>=', start_date))
            if end_date:
                domain.append(('date', '<=', end_date))

        # -------- server-side search --------
        if search_query:
            tokens = [t for t in search_query.split() if t]
            for token in tokens:
                domain += [
                    '|', '|', '|', '|', '|',
                    ('account_id.code', 'ilike', token),
                    ('account_id.name', 'ilike', token),
                    ('move_name', 'ilike', token),
                    ('name', 'ilike', token),
                    ('ref', 'ilike', token),
                    ('partner_id.name', 'ilike', token),
                ]

        # -------- per-account totals via read_group (no line load) --------
        grouped = self.env['account.move.line'].read_group(
            domain, ['debit:sum', 'credit:sum'], ['account_id'], lazy=False)
        account_meta_raw = []
        for g in grouped:
            if not g.get('account_id'):
                continue
            acc_id = g['account_id'][0]
            account_meta_raw.append({
                'id': acc_id,
                'debit': g.get('debit', 0.0) or 0.0,
                'credit': g.get('credit', 0.0) or 0.0,
            })

        acc_records = self.env['account.account'].browse(
            [a['id'] for a in account_meta_raw]).exists()
        acc_by_id = {a.id: a for a in acc_records}

        all_rows = []
        for a in account_meta_raw:
            acc = acc_by_id.get(a['id'])
            if not acc:
                continue
            key = f"{acc.code} {acc.name}"
            all_rows.append({
                'key': key,
                'id': acc.id,
                'code': acc.code or '',
                'name': acc.name or '',
                'debit': a['debit'],
                'credit': a['credit'],
            })
        all_rows.sort(key=lambda r: r['key'])

        total_accounts = len(all_rows)
        if limit is None:
            page_rows = all_rows[offset:]           # no cap — used by PDF/grand-total
        else:
            page_rows = all_rows[offset:offset + limit]
        page_keys = [r['key'] for r in page_rows]
        page_acc_ids = [r['id'] for r in page_rows]

        currency = self.env.company.currency_id.symbol

        # -------- opening balances for THIS PAGE's accounts only --------
        opening_balances = {}
        if start_date and page_acc_ids:
            opening_domain = [d for d in domain if d[0] != 'date']
            opening_domain += [('date', '<', start_date),
                            ('account_id', 'in', page_acc_ids)]
            opening_lines = self.env['account.move.line'].read_group(
                opening_domain, ['debit:sum', 'credit:sum'], ['account_id'])
            for row in opening_lines:
                acc_id = row['account_id'][0]
                opening_balances[acc_id] = ((row.get('debit', 0.0) or 0.0)
                                            - (row.get('credit', 0.0) or 0.0))

        # -------- lines for THIS PAGE's accounts only --------
        entries_by_account = defaultdict(list)
        if page_acc_ids:
            page_domain = [d for d in domain] + [('account_id', 'in', page_acc_ids)]
            move_lines = self.env['account.move.line'].search_read(
                page_domain,
                ['date', 'name', 'move_id', 'move_name', 'debit', 'credit',
                'partner_id', 'account_id', 'ref', 'journal_id'],
            )
        else:
            move_lines = []

        # split accounts (siblings in the same journal entry)
        move_ids = {l['move_id'][0] for l in move_lines if l.get('move_id')}
        move_account_map = defaultdict(set)
        split_account_ids = set()
        if move_ids:
            grouped2 = self.env['account.move.line'].read_group(
                [('move_id', 'in', list(move_ids))],
                ['account_id'], ['move_id', 'account_id'], lazy=False)
            for g in grouped2:
                if g.get('move_id') and g.get('account_id'):
                    move_account_map[g['move_id'][0]].add(g['account_id'][0])
                    split_account_ids.add(g['account_id'][0])

        split_account_map = {}
        if split_account_ids:
            for acc in self.env['account.account'].browse(list(split_account_ids)).exists():
                split_account_map[acc.id] = f"{acc.code} {acc.name}"

        def split_account_for(line):
            if not line.get('move_id') or not line.get('account_id'):
                return ''
            others = move_account_map[line['move_id'][0]] - {line['account_id'][0]}
            if not others:
                return ''
            return ', '.join(sorted(
                n for n in (split_account_map.get(a, '') for a in others) if n))

        account_totals = {}
        acc_by_key = {r['key']: r for r in page_rows}
        for line in sorted(move_lines, key=lambda l: (l.get('date') or '', l.get('id', 0))):
            acc_ref = line.get('account_id')
            if not acc_ref:
                continue
            acc_id = acc_ref[0]
            acc_rec = acc_by_id.get(acc_id)
            if not acc_rec:
                continue
            key = f"{acc_rec.code} {acc_rec.name}"
            line['split_account'] = split_account_for(line)
            line['location'] = ''   # dropped from main fetch; see note at bottom
            line['trx_type'] = line['journal_id'][1] if line.get('journal_id') else ''
            entries_by_account[key].append(line)
            t = account_totals.setdefault(key, {
                'total_debit': 0.0,
                'total_credit': 0.0,
                'currency_id': currency,
                'account_id': acc_id,
                'account_code': acc_rec.code or '',
                'account_name': acc_rec.name or key,
                'opening_balance': opening_balances.get(acc_id, 0.0),
            })
            t['total_debit'] += line.get('debit') or 0.0
            t['total_credit'] += line.get('credit') or 0.0

        # running balance per account
        for key, lines in entries_by_account.items():
            running = account_totals[key]['opening_balance']
            for line in lines:
                running += (line.get('debit') or 0.0) - (line.get('credit') or 0.0)
                line['running_balance'] = running

        # ensure every account in the page has an entry (even if no lines matched search)
        for key in page_keys:
            if key not in entries_by_account:
                entries_by_account[key] = []
            if key not in account_totals:
                r = acc_by_key[key]
                account_totals[key] = {
                    'total_debit': r['debit'],
                    'total_credit': r['credit'],
                    'currency_id': currency,
                    'account_id': r['id'],
                    'account_code': r['code'],
                    'account_name': r['name'],
                    'opening_balance': opening_balances.get(r['id'], 0.0),
                }

        result = dict(entries_by_account)
        result['account'] = page_keys
        result['account_totals'] = account_totals
        result['total_accounts'] = total_accounts
        result['has_more'] = offset + limit < total_accounts
        result['offset'] = offset

        if include_filter_values and offset == 0:
            result['journal_ids'] = self.env['account.journal'].search_read([], ['name'])
            result['analytic_ids'] = self.env['account.analytic.account'].search_read([], ['name'])
        else:
            result['journal_ids'] = []
            result['analytic_ids'] = []

        return result

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

        headers = ['Sr', 'Account Code', 'Account Name', 'Split Account', 'Location', 'Date',
                   'Trx Type', 'V.No', 'Ref No.', 'Name', 'Description',
                   'Debit', 'Credit', 'Balance']
        widths = [6, 16, 25, 30, 50, 12, 14, 18, 14, 22, 34, 14, 14, 16]
        last_col = len(headers) - 1

        for idx, w in enumerate(widths):
            sheet.set_column(idx, idx, w)
        sheet.set_default_row(20)

        # ==================== Neutral / clean format palette ====================
        company_fmt = workbook.add_format({
            'bold': True, 'font_size': 16, 'font_color': '#1A1A1A',
            'align': 'left', 'valign': 'vcenter'})

        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 13, 'font_color': '#333333',
            'align': 'left', 'valign': 'vcenter'})

        subtitle_fmt = workbook.add_format({
            'font_size': 10, 'font_color': '#666666',
            'align': 'left', 'valign': 'vcenter'})

        printed_date_fmt = workbook.add_format({
            'bold': True, 'font_size': 9, 'font_color': '#666666',
            'align': 'right', 'valign': 'vcenter'})

        section_header_fmt = workbook.add_format({
            'bg_color': '#333333', 'font_color': '#FFFFFF',
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'font_size': 10, 'border': 1, 'border_color': '#333333'})

        banner_fmt = workbook.add_format({
            'bg_color': '#E8E8E8', 'font_color': '#1A1A1A',
            'bold': True, 'font_size': 10, 'border': 1,
            'border_color': '#BFBFBF', 'align': 'left', 'valign': 'vcenter'})
        banner_fmt.set_indent(1)

        opening_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'bg_color': '#F2F2F2',
            'font_color': '#1A1A1A', 'border': 1, 'border_color': '#BFBFBF',
            'valign': 'vcenter'})
        opening_num_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'bg_color': '#F2F2F2',
            'font_color': '#1A1A1A', 'border': 1, 'border_color': '#BFBFBF',
            'num_format': '#,##0.00', 'valign': 'vcenter'})

        line_fmt = workbook.add_format({
            'font_size': 10, 'border': 1, 'border_color': '#D9D9D9',
            'valign': 'vcenter'})
        name_fmt = workbook.add_format({
            'font_size': 10, 'border': 1, 'border_color': '#D9D9D9',
            'text_wrap': True, 'valign': 'vcenter'})
        num_fmt = workbook.add_format({
            'font_size': 10, 'border': 1, 'border_color': '#D9D9D9',
            'num_format': '#,##0.00', 'valign': 'vcenter'})

        total_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'bg_color': '#E8E8E8',
            'font_color': '#1A1A1A', 'border': 1, 'border_color': '#BFBFBF',
            'top': 2, 'top_color': '#333333', 'valign': 'vcenter'})
        total_num_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'bg_color': '#E8E8E8',
            'font_color': '#1A1A1A', 'border': 1, 'border_color': '#BFBFBF',
            'top': 2, 'top_color': '#333333',
            'num_format': '#,##0.00', 'valign': 'vcenter'})

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

        underline_fmt = workbook.add_format({'bottom': 1, 'bottom_color': '#333333'})
        sheet.merge_range(3, 0, 3, last_col, '', underline_fmt)
        sheet.set_row(3, 4)

        row = 5
        if report_accounts:
            if report_action == 'dynamic_accounts_report.action_general_ledger':
                for account in report_accounts:
                    account_total = report_totals.get(account) or {}
                    account_label = account if account != 'false' else 'Unknown Account'
                    lines_for_account = report_data.get(account, [])

                    computed_debit = 0.0
                    computed_credit = 0.0
                    for rec in lines_for_account:
                        record = rec[0] if isinstance(rec, list) else rec
                        computed_debit += record.get('debit', 0.0) or 0.0
                        computed_credit += record.get('credit', 0.0) or 0.0

                    opening_balance = account_total.get('opening_balance', 0.0)
                    closing = opening_balance + computed_debit - computed_credit

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
                    sheet.merge_range(row, 1, row, 10, 'OPENING BALANCE', opening_fmt)
                    sheet.write(row, 11, '', opening_fmt)
                    sheet.write(row, 12, '', opening_fmt)
                    sheet.write(row, 13, opening_balance, opening_num_fmt)
                    row += 1

                    # Transaction lines
                    for sr, rec in enumerate(lines_for_account, start=1):
                        record = rec[0] if isinstance(rec, list) else rec
                        partner = record.get('partner_id')
                        partner_name = partner[1] if isinstance(partner, (list, tuple)) and len(partner) > 1 else ''
                        sheet.write(row, 0, sr, line_fmt)
                        sheet.write(row, 1, account_total.get('account_code', ''), line_fmt)
                        sheet.write(row, 2, account_total.get('account_name', ''), name_fmt)
                        sheet.write(row, 3, record.get('split_account', ''), line_fmt)
                        sheet.write(row, 4, record.get('location', ''), line_fmt)
                        sheet.write(row, 5, record.get('date', ''), line_fmt)
                        sheet.write(row, 6, record.get('trx_type', ''), line_fmt)
                        sheet.write(row, 7, record.get('move_name', ''), line_fmt)
                        sheet.write(row, 8, record.get('ref', ''), line_fmt)
                        sheet.write(row, 9, partner_name, line_fmt)
                        sheet.write(row, 10, record.get('name', ''), line_fmt)
                        sheet.write(row, 11, record.get('debit', 0.0) or '', num_fmt)
                        sheet.write(row, 12, record.get('credit', 0.0) or '', num_fmt)
                        sheet.write(row, 13, record.get('running_balance', 0.0), num_fmt)
                        sheet.set_row(row, 30)
                        row += 1

                    # Per-account totals
                    sheet.merge_range(row, 0, row, 10, 'Total', total_fmt)
                    sheet.write(row, 11, computed_debit, total_num_fmt)
                    sheet.write(row, 12, computed_credit, total_num_fmt)
                    sheet.write(row, 13, closing, total_num_fmt)
                    sheet.set_row(row, 24)
                    row += 1

                    # Closing Balance row
                    sheet.write(row, 0, '', opening_fmt)
                    sheet.merge_range(row, 1, row, 10, 'CLOSING BALANCE', opening_fmt)
                    sheet.write(row, 11, '', opening_fmt)
                    sheet.write(row, 12, '', opening_fmt)
                    sheet.write(row, 13, closing, opening_num_fmt)
                    row += 2  # blank spacer row between account blocks

                # ================= Grand totals =================
                # Period-only debit / credit (opening is NOT inside these).
                grand_opening = sum(
                    (report_totals.get(acc) or {}).get('opening_balance', 0.0)
                    for acc in report_accounts
                )
                grand_debit = 0.0
                grand_credit = 0.0
                for acc in report_accounts:
                    for rec in report_data.get(acc, []):
                        record = rec[0] if isinstance(rec, list) else rec
                        grand_debit += record.get('debit', 0.0) or 0.0
                        grand_credit += record.get('credit', 0.0) or 0.0

                grand_closing   = grand_opening + grand_debit - grand_credit
                period_balance  = grand_debit - grand_credit    # without opening

                # Row 1 — GRAND TOTAL (with opening balance)
                sheet.merge_range(row, 0, row, 10, 'GRAND TOTAL', grand_total_fmt)
                sheet.write(row, 11, grand_debit,   grand_total_num_fmt)
                sheet.write(row, 12, grand_credit,  grand_total_num_fmt)
                sheet.write(row, 13, grand_closing, grand_total_num_fmt)
                sheet.set_row(row, 26)
                row += 1

                # Row 2 — TOTAL (Without Opening Balance)
                sheet.merge_range(row, 0, row, 10,
                                  'TOTAL (Without Opening Balance)', grand_total_fmt)
                sheet.write(row, 11, grand_debit,     grand_total_num_fmt)
                sheet.write(row, 12, grand_credit,    grand_total_num_fmt)
                sheet.write(row, 13, period_balance,  grand_total_num_fmt)
                sheet.set_row(row, 26)
                row += 1

        # Freeze the header rows so they stay visible while scrolling
        sheet.freeze_panes(5, 0)

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()