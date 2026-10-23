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
import datetime
import xlsxwriter
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.date_utils import get_month, get_fiscal_year, get_quarter, \
    subtract


class ProfitLossReport(models.TransientModel):
    """For creating Profit and Loss and Balance sheet report."""
    _name = 'dynamic.balance.sheet.report'
    _description = 'Profit Loss Report'

    company_id = fields.Many2one('res.company', required=True,
                                 default=lambda self: self.env.company,
                                 help='Select the company to which this'
                                      'record belongs.')
    journal_ids = fields.Many2many('account.journal',
                                   string='Journals', required=True,
                                   default=[],
                                   help='Select one or more journals.')
    account_ids = fields.Many2many("account.account", string="Accounts",
                                   help='Select one or more accounts.')
    analytic_ids = fields.Many2many(
        "account.analytic.account", string="Analytic Accounts",
        help="Analytic accounts associated with the current record.")
    target_move = fields.Selection([('posted', 'Posted'), ('draft', 'Draft')],
                                   string='Target Move', required=True,
                                   default='posted',
                                   help='Select the target move status.')
    date_from = fields.Date(string="Start date",
                            help="Specify the start date.")
    date_to = fields.Date(string="End date", help="Specify the end date.")

    # Simple cache so that load_data / print_pdf / print_xlsx don't all
    # recompute the same report.
    cache_key = fields.Char()
    cache_payload = fields.Text()

    # Account types whose natural sign is credit (i.e. we flip debit-credit).
    _INCOME_LIKE_TYPES = {
        'income', 'income_other',
        'liability_payable', 'liability_current', 'liability_non_current',
        'equity', 'equity_unaffected',
    }

    _ACCOUNT_TYPES = [
        'income', 'income_other', 'expense', 'expense_depreciation',
        'expense_direct_cost',
        'asset_receivable', 'asset_cash', 'asset_current',
        'asset_non_current', 'asset_prepayments', 'asset_fixed',
        'liability_payable', 'liability_credit_card', 'liability_current',
        'liability_non_current',
        'equity', 'equity_unaffected',
    ]

    @api.model_create_multi
    def create(self, vals):
        """Create the (singleton) wizard. Filter values arrive later via
        ``filter()``, so we deliberately ignore the incoming payload and
        create with defaults."""
        return super().create({})

    # ------------------------------------------------------------------ #
    #  Core computation                                                   #
    # ------------------------------------------------------------------ #
    @api.model
    def view_report(self, option, comparison, comparison_type):
        """Build the Profit & Loss report payload.

        :returns: ``(data, filters, datas)`` tuple
        """
        rec = self.browse(option)

        # Cache hit?
        key = self._cache_signature(rec, comparison, comparison_type)
        if rec.cache_key == key and rec.cache_payload:
            try:
                data, filters, datas = json.loads(rec.cache_payload)
                return data, filters, datas
            except (ValueError, TypeError):
                pass  # fall through and recompute

        if rec.target_move == 'draft':
            target_move = ['posted', 'draft']
        else:
            target_move = ['posted']

        datas = []
        if comparison:
            for count in range(0, int(comparison) + 1):
                if comparison_type == "month":
                    period_from = (datetime.date.today() - datetime.timedelta(
                        days=30 * count)).strftime('%Y-%m-01')
                    period_to = (datetime.date.today() - datetime.timedelta(
                        days=30 * count)).strftime('%Y-%m-12')
                else:  # "year"
                    period_from = f'{fields.Date.today().year - count}-01-01'
                    period_to = f'{fields.Date.today().year - count}-12-31'

                data, _ = self._compute_period(
                    rec, target_move, period_from, period_to)
                datas.append(data)
        else:
            current_year = fields.Date.today().year
            date_from = rec.date_from or f'{current_year}-01-01'
            date_to = rec.date_to or f'{current_year}-12-31'
            data, _ = self._compute_period(rec, target_move, date_from, date_to)
            datas.append(data)

        data = datas[0]  # report payload for single-period callers
        filters = self._get_filter_data()

        rec.write({
            'cache_key': key,
            'cache_payload': json.dumps([data, filters, datas]),
        })
        return data, filters, datas

    # ------------------------------------------------------------------ #
    #  Per-period computation                                             #
    # ------------------------------------------------------------------ #
    def _compute_period(self, rec, target_move, date_from, date_to):
        """Return (data_dict, account_entries) for a single period."""
        # ---- 1. Build the search domain directly. All the field-level
        #         filtering that used to be done with ``.filtered(...)``
        #         now happens in SQL.
        domain = [
            ('parent_state', 'in', target_move),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]
        if rec.journal_ids:
            domain.append(('journal_id', 'in', rec.journal_ids.ids))
        if rec.account_ids:
            domain.append(('account_id', 'in', rec.account_ids.ids))

        account_move_lines = self.env['account.move.line'].search(domain)

        # ---- 2. Analytic filter. There is no clean SQL way to test keys
        #         of a JSONB column against a list of ints in every PG
        #         version we support, so keep it in Python but operate
        #         with ints only (never eval() user data).
        if rec.analytic_ids:
            wanted = set(rec.analytic_ids.ids)
            account_move_lines = account_move_lines.filtered(
                lambda l: l.analytic_distribution and any(
                    int(k) in wanted for k in l.analytic_distribution.keys()
                )
            )

        # ---- 3. Single O(N) pass over the lines -> bucket by account.
        buckets = self._build_account_buckets(account_move_lines)

        # ---- 4. Fetch accounts once, group by account_type.
        all_accounts = self.env['account.account'].search(
            [('account_type', 'in', self._ACCOUNT_TYPES)])
        accounts_by_type = {}
        for acc in all_accounts:
            accounts_by_type.setdefault(acc.account_type, []).append(acc)

        account_entries = {}
        for account_type in self._ACCOUNT_TYPES:
            account_entries[account_type] = self._get_entries(
                buckets,
                accounts_by_type.get(account_type, []),
                account_type,
            )

        # ---- 5. Totals. Same maths as before but reading directly from
        #         the numeric amounts instead of the formatted strings.
        def _sum(*types):
            total = 0.0
            for t in types:
                # account_entries[t][1] is the formatted total; use the
                # numeric value stored next to it.
                total += account_entries[t][2]
            return total

        total_income = (
            _sum('income', 'income_other') - _sum('expense_direct_cost')
        )
        total_expense = _sum('expense', 'expense_depreciation')
        total_current_asset = _sum(
            'asset_receivable', 'asset_current', 'asset_cash',
            'asset_prepayments')
        total_assets = total_current_asset + _sum(
            'asset_fixed', 'asset_non_current')
        total_current_liability = _sum(
            'liability_current', 'liability_payable')
        total_liability = total_current_liability + _sum(
            'liability_non_current')
        total_unallocated_earning = (
            (total_income - total_expense) + _sum('equity_unaffected')
        )
        total_equity = total_unallocated_earning + _sum('equity')
        total = total_liability + total_equity

        data = {
            'total': total_income - total_expense,
            'total_expense': "{:,.2f}".format(total_expense),
            'total_income': "{:,.2f}".format(total_income),
            'total_current_asset': "{:,.2f}".format(total_current_asset),
            'total_assets': "{:,.2f}".format(total_assets),
            'total_current_liability': "{:,.2f}".format(
                total_current_liability),
            'total_liability': "{:,.2f}".format(total_liability),
            'total_earnings': "{:,.2f}".format(total_income - total_expense),
            'total_unallocated_earning': "{:,.2f}".format(
                total_unallocated_earning),
            'total_equity': "{:,.2f}".format(total_equity),
            'total_balance': "{:,.2f}".format(total),
        }
        # account_entries values are (entries, formatted_total, numeric_total)
        # but the JSON payload historically exposed (entries, formatted_total).
        # Strip the third element to keep the front-end / XLSX template happy.
        for k, v in account_entries.items():
            data[k] = (v[0], v[1])
        return data, account_entries

    def _build_account_buckets(self, account_move_lines):
        """Single-pass aggregation: ``{account_id: [debit_sum, credit_sum]}``."""
        buckets = {}
        for line in account_move_lines:
            aid = line.account_id.id
            b = buckets.get(aid)
            if b is None:
                buckets[aid] = [line.debit, line.credit]
            else:
                b[0] += line.debit
                b[1] += line.credit
        return buckets

    def _get_entries(self, buckets, accounts, account_type):
        """Return ``(entries, formatted_total, numeric_total)``.

        Uses a pre-built bucket dict so the whole report is O(lines + accounts)
        instead of O(lines × accounts) as before.
        """
        sign = -1.0 if account_type in self._INCOME_LIKE_TYPES else 1.0
        entries = []
        total = 0.0
        for account in accounts:
            b = buckets.get(account.id)
            amount = sign * (b[0] - b[1]) if b else 0.0
            entries.append({
                'name': "{} - {}".format(account.code, account.name),
                'amount': "{:,.2f}".format(amount),
            })
            total += amount
        return entries, "{:,.2f}".format(total), total

    # ------------------------------------------------------------------ #
    #  Filters                                                            #
    # ------------------------------------------------------------------ #
    def filter(self, vals):
        """Update the filter criteria based on the provided values."""
        filter = []
        today = fields.Date.today()
        if vals == 'month':
            vals = {
                'date_from': get_month(today)[0].strftime("%Y-%m-%d"),
                'date_to': get_month(today)[1].strftime("%Y-%m-%d"),
            }
        elif vals == 'quarter':
            vals = {
                'date_from': get_quarter(today)[0].strftime("%Y-%m-%d"),
                'date_to': get_quarter(today)[1].strftime("%Y-%m-%d"),
            }
        elif vals == 'year':
            vals = {
                'date_from': get_fiscal_year(today)[0].strftime("%Y-%m-%d"),
                'date_to': get_fiscal_year(today)[1].strftime("%Y-%m-%d"),
            }
        elif vals == 'last-month':
            last_month_date = subtract(today, months=1)
            vals = {
                'date_from': get_month(last_month_date)[0].strftime(
                    "%Y-%m-%d"),
                'date_to': get_month(last_month_date)[1].strftime("%Y-%m-%d"),
            }
        elif vals == 'last-quarter':
            last_quarter_date = subtract(today, months=3)
            vals = {
                'date_from': get_quarter(last_quarter_date)[0].strftime(
                    "%Y-%m-%d"),
                'date_to': get_quarter(last_quarter_date)[1].strftime(
                    "%Y-%m-%d"),
            }
        elif vals == 'last-year':
            last_year_date = subtract(today, years=1)
            vals = {
                'date_from': get_fiscal_year(last_year_date)[0].strftime(
                    "%Y-%m-%d"),
                'date_to': get_fiscal_year(last_year_date)[1].strftime(
                    "%Y-%m-%d"),
            }

        if 'date_from' in vals:
            self.write({'date_from': vals['date_from']})
        if 'date_to' in vals:
            self.write({'date_to': vals['date_to']})
        if 'journal_ids' in vals:
            if int(vals['journal_ids']) in self.journal_ids.mapped('id'):
                self.write({'journal_ids': [(3, int(vals['journal_ids']))]})
            else:
                self.write({'journal_ids': [(4, int(vals['journal_ids']))]})
            filter.append({'journal_ids': self.journal_ids.mapped('code')})
        if 'account_ids' in vals:
            if int(vals['account_ids']) in self.account_ids.mapped('id'):
                self.write({'account_ids': [(3, int(vals['account_ids']))]})
            else:
                self.write({'account_ids': [(4, int(vals['account_ids']))]})
            filter.append({'account_ids': self.account_ids.mapped('name')})
        if 'analytic_ids' in vals:
            if int(vals['analytic_ids']) in self.analytic_ids.mapped('id'):
                self.write(
                    {'analytic_ids': [(3, int(vals['analytic_ids']))]})
            else:
                self.write(
                    {'analytic_ids': [(4, int(vals['analytic_ids']))]})
            filter.append({'analytic_ids': self.analytic_ids.mapped('name')})
        if 'target' in vals:
            self.write({'target_move': vals['target']})
            filter.append({'target_move': self.target_move})

        # Any filter change invalidates the cache.
        self.write({'cache_key': False, 'cache_payload': False})
        return filter

    def _get_filter_data(self):
        """Return the dropdown contents for journals / accounts / analytics.

        Restricted to the current company where the model supports it and
        uses ``search_read`` to avoid loading whole records just to build
        a two-key dict.
        """
        company = self.company_id or self.env.company

        journal_recs = self.env['account.journal'].search_read(
            [('company_id', '=', company.id)], ['name'])
        journal = [{'id': r['id'], 'name': r['name']} for r in journal_recs]

        account_domain = []
        if 'company_ids' in self.env['account.account']._fields:
            account_domain = [('company_ids', 'in', company.id)]
        elif 'company_id' in self.env['account.account']._fields:
            account_domain = [('company_id', '=', company.id)]
        account_recs = self.env['account.account'].search_read(
            account_domain, ['name'])
        account = [{'id': r['id'], 'name': r['name']} for r in account_recs]

        analytic_recs = self.env['account.analytic.account'].search_read(
            [], ['name'])
        analytic = [{'id': r['id'], 'name': r['name']} for r in analytic_recs]

        return {
            'journal': journal,
            'account': account,
            'analytic': analytic,
        }

    # ------------------------------------------------------------------ #
    #  Cache helpers                                                      #
    # ------------------------------------------------------------------ #
    def _cache_signature(self, rec, comparison, comparison_type):
        return "|".join(str(x) for x in [
            comparison, comparison_type,
            rec.date_from, rec.date_to, rec.target_move,
            rec.journal_ids.ids, rec.account_ids.ids, rec.analytic_ids.ids,
        ])

    # ------------------------------------------------------------------ #
    #  Comparison helpers (unchanged logic)                               #
    # ------------------------------------------------------------------ #
    @api.model
    def comparison_filter(self, options, count):
        today = fields.Date.today()
        if not count:
            raise ValidationError(_("Please select the count."))
        last_month_date_list = []
        for i in range(1, int(count) + 1):
            last_month_date = subtract(today, months=i)
            vals = {
                'date_from': get_month(last_month_date)[0].strftime(
                    "%Y-%m-%d"),
                'date_to': get_month(last_month_date)[1].strftime("%Y-%m-%d"),
            }
            last_month_date_list.append(vals)
        return last_month_date_list

    @api.model
    def comparison_filter_year(self, options, count):
        today = fields.Date.today()
        if not count:
            raise ValidationError(_("Please select the count."))
        last_year_date_list = []
        for i in range(1, int(count) + 1):
            last_year_date = subtract(today, years=i)
            vals = {
                'date_from': get_fiscal_year(last_year_date)[0].strftime(
                    "%Y-%m-%d"),
                'date_to': get_fiscal_year(last_year_date)[1].strftime(
                    "%Y-%m-%d"),
            }
            last_year_date_list.append(vals)
        return last_year_date_list

    @api.model
    def get_xlsx_report(self, data, response, report_name, report_action):
        """Generate and return an XLSX report based on the provided data."""
        data = json.loads(data)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet()
        sub_heading = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '10px',
             'border': 1,
             'border_color': 'black'})
        side_heading_sub = workbook.add_format(
            {'align': 'left', 'bold': True, 'font_size': '10px',
             'border': 1,
             'border_color': 'black'})
        side_heading_sub.set_indent(1)
        txt_name = workbook.add_format({'font_size': '10px', 'border': 1})
        txt_name_left = workbook.add_format(
            {'align': 'left', 'font_size': '10px', 'border': 1})
        txt_name.set_indent(2)
        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 1, 20)
        sheet.set_column(2, 2, 15)
        sheet.set_column(3, 3, 15)
        col = 0
        sheet.write('A3:b4', report_name, sub_heading)
        sheet.write(5, col, '', sub_heading)
        for date in data['year']:
            sheet.write(4, col + 1, date, sub_heading)
            sheet.write(5, col + 1, 'Balance', sub_heading)
            col += 1
        col = 0
        if data:
            if report_action == 'dynamic_accounts_report.action_dynamic_profit_and_loss':
                sheet.write(6, col, 'Net Profit', sub_heading)
                for datas in data['datas']:
                    sheet.write(6, col + 1, datas['total'], side_heading_sub)
                    col += 1
                col = 0
                sheet.write(7, col, 'Income', side_heading_sub)
                sheet.write(7, col + 1, ' ', side_heading_sub)
                sheet.write(8, col, 'Operating Income', txt_name_left)
                for datas in data['datas']:
                    sheet.write(8, col + 1, datas['income'][1], txt_name)
                    col += 1
                row = 8
                index = 0
                for datas in data['datas']:
                    if index == 0:
                        for accounts in datas['income'][0]:
                            account_name = accounts['name']
                            account_value = 0
                            for datas in data['datas']:
                                for account in datas['income'][0]:
                                    if account_name == account['name'] and \
                                            account['amount'] != '0.00':
                                        account_value = 1
                            if account_value == 1:
                                row += 1
                                col = 0
                                sheet.write(row, col, accounts['name'],
                                            txt_name)
                                for datas in data['datas']:
                                    for account in datas['income'][0]:
                                        if account_name == account['name']:
                                            sheet.write(row, col + 1,
                                                        account['amount'],
                                                        txt_name)
                                            col += 1
                    index += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Cost of Revenue', txt_name_left)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['expense_direct_cost'][1],
                                txt_name)
                    col += 1
                index = 0
                for datas in data['datas']:
                    if index == 0:
                        for accounts in datas['expense_direct_cost'][0]:
                            account_name = accounts['name']
                            account_value = 0
                            for datas in data['datas']:
                                for account in datas['expense_direct_cost'][0]:
                                    if account_name == account['name'] and \
                                            account['amount'] != '0.00':
                                        account_value = 1
                            if account_value == 1:
                                row += 1
                                col = 0
                                sheet.write(row, col, accounts['name'],
                                            txt_name)
                                for datas in data['datas']:
                                    for account in \
                                            datas['expense_direct_cost'][0]:
                                        if account_name == account['name']:
                                            sheet.write(row, col + 1,
                                                        account['amount'],
                                                        txt_name)
                                            col += 1
                    index += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Other Income', txt_name_left)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['income_other'][1],
                                txt_name)
                    col += 1
                index = 0
                for datas in data['datas']:
                    if index == 0:
                        for accounts in datas['income_other'][0]:
                            account_name = accounts['name']
                            account_value = 0
                            for datas in data['datas']:
                                for account in datas['income_other'][0]:
                                    if account_name == account['name'] and \
                                            account['amount'] != '0.00':
                                        account_value = 1
                            if account_value == 1:
                                row += 1
                                col = 0
                                sheet.write(row, col, accounts['name'],
                                            txt_name)
                                for datas in data['datas']:
                                    for account in datas['income_other'][0]:
                                        if account_name == account['name']:
                                            sheet.write(row, col + 1,
                                                        account['amount'],
                                                        txt_name)
                                            col += 1
                    index += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Total Income', side_heading_sub)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['total_income'],
                                side_heading_sub)
                    col += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Expense', side_heading_sub)
                sheet.write(row, col + 1, '', side_heading_sub)
                row += 1
                col = 0
                sheet.write(row, col, 'Expense', txt_name_left)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['expense'][1], txt_name)
                    col += 1
                index = 0
                for datas in data['datas']:
                    if index == 0:
                        for accounts in datas['expense'][0]:
                            account_name = accounts['name']
                            account_value = 0
                            for datas in data['datas']:
                                for account in datas['expense'][0]:
                                    if account_name == account['name'] and \
                                            account['amount'] != '0.00':
                                        account_value = 1
                            if account_value == 1:
                                row += 1
                                col = 0
                                sheet.write(row, col, accounts['name'],
                                            txt_name)
                                for datas in data['datas']:
                                    for account in datas['expense'][0]:
                                        if account_name == account['name']:
                                            sheet.write(row, col + 1,
                                                        account['amount'],
                                                        txt_name)
                                            col += 1
                    index += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Depreciation', txt_name_left)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['expense_depreciation'][1],
                                txt_name)
                    col += 1
                index = 0
                for datas in data['datas']:
                    if index == 0:
                        for accounts in datas['expense_depreciation'][0]:
                            account_name = accounts['name']
                            account_value = 0
                            for datas in data['datas']:
                                for account in datas['expense_depreciation'][
                                    0]:
                                    if account_name == account['name'] and \
                                            account['amount'] != '0.00':
                                        account_value = 1
                            if account_value == 1:
                                row += 1
                                col = 0
                                sheet.write(row, col, accounts['name'],
                                            txt_name)
                                for datas in data['datas']:
                                    for account in \
                                            datas['expense_depreciation'][
                                                0]:
                                        if account_name == account['name']:
                                            sheet.write(row, col + 1,
                                                        account['amount'],
                                                        txt_name)
                                            col += 1
                    index += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Total Expenses', side_heading_sub)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['total_expense'],
                                side_heading_sub)
                    col += 1
            else:
                sheet.write(6, col, 'ASSETS', sub_heading)
                sheet.write(6, col + 1, ' ', side_heading_sub)
                sheet.write(7, col, 'Current Assets', side_heading_sub)
                sheet.write(7, col + 1, ' ', side_heading_sub)
                sheet.write(8, col, 'Bank and Cash Accounts', txt_name_left)
                for datas in data['datas']:
                    sheet.write(8, col + 1, datas['asset_cash'][1], txt_name)
                    col += 1
                row = 8
                index = 0
                for datas in data['datas']:
                    if index == 0:
                        for accounts in datas['asset_cash'][0]:
                            account_name = accounts['name']
                            account_value = 0
                            for datas in data['datas']:
                                for account in datas['asset_cash'][0]:
                                    if account_name == account['name'] and \
                                            account['amount'] != '0.00':
                                        account_value = 1
                            if account_value == 1:
                                row += 1
                                col = 0
                                sheet.write(row, col, accounts['name'],
                                            txt_name)
                                for datas in data['datas']:
                                    for account in datas['asset_cash'][0]:
                                        if account_name == account['name']:
                                            sheet.write(row, col + 1,
                                                        account['amount'],
                                                        txt_name)
                                            col += 1
                    index += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Receivables', txt_name_left)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['asset_receivable'][1],
                                txt_name)
                    col += 1
                index = 0
                for datas in data['datas']:
                    if index == 0:
                        for accounts in datas['asset_receivable'][0]:
                            account_name = accounts['name']
                            account_value = 0
                            for datas in data['datas']:
                                for account in datas['asset_receivable'][0]:
                                    if account_name == account['name'] and \
                                            account['amount'] != '0.00':
                                        account_value = 1
                            if account_value == 1:
                                row += 1
                                col = 0
                                sheet.write(row, col, accounts['name'],
                                            txt_name)
                                for datas in data['datas']:
                                    for account in datas['asset_receivable'][
                                        0]:
                                        if account_name == account['name']:
                                            sheet.write(row, col + 1,
                                                        account['amount'],
                                                        txt_name)
                                            col += 1
                    index += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Current Assets', txt_name_left)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['asset_current'][1],
                                txt_name)
                    col += 1
                index = 0
                for datas in data['datas']:
                    if index == 0:
                        for accounts in datas['asset_current'][0]:
                            account_name = accounts['name']
                            account_value = 0
                            for datas in data['datas']:
                                for account in datas['asset_current'][0]:
                                    if account_name == account['name'] and \
                                            account['amount'] != '0.00':
                                        account_value = 1
                            if account_value == 1:
                                row += 1
                                col = 0
                                sheet.write(row, col, accounts['name'],
                                            txt_name)
                                for datas in data['datas']:
                                    for account in datas['asset_current'][0]:
                                        if account_name == account['name']:
                                            sheet.write(row, col + 1,
                                                        account['amount'],
                                                        txt_name)
                                            col += 1
                    index += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Prepayments', txt_name_left)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['asset_prepayments'][1],
                                txt_name)
                    col += 1
                index = 0
                for datas in data['datas']:
                    if index == 0:
                        for accounts in datas['asset_prepayments'][0]:
                            account_name = accounts['name']
                            account_value = 0
                            for datas in data['datas']:
                                for account in datas['asset_prepayments'][0]:
                                    if account_name == account['name'] and \
                                            account['amount'] != '0.00':
                                        account_value = 1
                            if account_value == 1:
                                row += 1
                                col = 0
                                sheet.write(row, col, accounts['name'],
                                            txt_name)
                                for datas in data['datas']:
                                    for account in datas['asset_prepayments'][
                                        0]:
                                        if account_name == account['name']:
                                            sheet.write(row, col + 1,
                                                        account['amount'],
                                                        txt_name)
                                            col += 1
                    index += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Total Current Assets', side_heading_sub)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['total_current_asset'],
                                side_heading_sub)
                    col += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Plus Fixed Assets', txt_name_left)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['asset_fixed'][1],
                                txt_name)
                    col += 1
                index = 0
                for datas in data['datas']:
                    if index == 0:
                        for accounts in datas['asset_fixed'][0]:
                            account_name = accounts['name']
                            account_value = 0
                            for datas in data['datas']:
                                for account in datas['asset_fixed'][0]:
                                    if account_name == account['name'] and \
                                            account['amount'] != '0.00':
                                        account_value = 1
                            if account_value == 1:
                                row += 1
                                col = 0
                                sheet.write(row, col, accounts['name'],
                                            txt_name)
                                for datas in data['datas']:
                                    for account in datas['asset_fixed'][
                                        0]:
                                        if account_name == account['name']:
                                            sheet.write(row, col + 1,
                                                        account['amount'],
                                                        txt_name)
                                            col += 1
                    index += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Plus Non-current Assets', txt_name_left)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['asset_non_current'][1],
                                txt_name)
                    col += 1
                index = 0
                for datas in data['datas']:
                    if index == 0:
                        for accounts in datas['asset_non_current'][0]:
                            account_name = accounts['name']
                            account_value = 0
                            for datas in data['datas']:
                                for account in datas['asset_non_current'][0]:
                                    if account_name == account['name'] and \
                                            account['amount'] != '0.00':
                                        account_value = 1
                            if account_value == 1:
                                row += 1
                                col = 0
                                sheet.write(row, col, accounts['name'],
                                            txt_name)
                                for datas in data['datas']:
                                    for account in datas['asset_non_current'][
                                        0]:
                                        if account_name == account['name']:
                                            sheet.write(row, col + 1,
                                                        account['amount'],
                                                        txt_name)
                                            col += 1
                    index += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Total Assets', side_heading_sub)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['total_assets'],
                                side_heading_sub)
                    col += 1
                col = 0
                row += 1
                sheet.write(row, col, 'LIABILITIES', sub_heading)
                sheet.write(row, col + 1, '', sub_heading)
                row += 1
                sheet.write(row, col, 'Current Liabilities', side_heading_sub)
                sheet.write(row, col + 1, ' ', side_heading_sub)
                row += 1
                sheet.write(row, col, 'Current Liabilities', txt_name_left)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['liability_current'][1],
                                txt_name)
                    col += 1
                index = 0
                for datas in data['datas']:
                    if index == 0:
                        for accounts in datas['liability_current'][0]:
                            account_name = accounts['name']
                            account_value = 0
                            for datas in data['datas']:
                                for account in datas['liability_current'][0]:
                                    if account_name == account['name'] and \
                                            account['amount'] != '0.00':
                                        account_value = 1
                            if account_value == 1:
                                row += 1
                                col = 0
                                sheet.write(row, col, accounts['name'],
                                            txt_name)
                                for datas in data['datas']:
                                    for account in datas['liability_current'][
                                        0]:
                                        if account_name == account['name']:
                                            sheet.write(row, col + 1,
                                                        account['amount'],
                                                        txt_name)
                                            col += 1
                    index += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Payables', txt_name_left)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['liability_payable'][1],
                                txt_name)
                    col += 1
                index = 0
                for datas in data['datas']:
                    if index == 0:
                        for accounts in datas['liability_payable'][0]:
                            account_name = accounts['name']
                            account_value = 0
                            for datas in data['datas']:
                                for account in datas['liability_payable'][0]:
                                    if account_name == account['name'] and \
                                            account['amount'] != '0.00':
                                        account_value = 1
                            if account_value == 1:
                                row += 1
                                col = 0
                                sheet.write(row, col, accounts['name'],
                                            txt_name)
                                for datas in data['datas']:
                                    for account in datas['liability_payable'][
                                        0]:
                                        if account_name == account['name']:
                                            sheet.write(row, col + 1,
                                                        account['amount'],
                                                        txt_name)
                                            col += 1
                    index += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Total Current Liabilities',
                            side_heading_sub)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['total_current_liability'],
                                side_heading_sub)
                    col += 1
                col = 0
                row += 1
                sheet.write(row, col, 'Plus Non-current Liabilities',
                            txt_name_left)
                for datas in data['datas']:
                    sheet.write(row, col + 1,
                                datas['liability_non_current'][1],
                                txt_name)
                    col += 1
                index = 0
                for datas in data['datas']:
                    if index == 0:
                        for accounts in datas['liability_non_current'][0]:
                            account_name = accounts['name']
                            account_value = 0
                            for datas in data['datas']:
                                for account in datas['liability_non_current'][
                                    0]:
                                    if account_name == account['name'] and \
                                            account['amount'] != '0.00':
                                        account_value = 1
                            if account_value == 1:
                                row += 1
                                col = 0
                                sheet.write(row, col, accounts['name'],
                                            txt_name)
                                for datas in data['datas']:
                                    for account in \
                                            datas['liability_non_current'][
                                                0]:
                                        if account_name == account['name']:
                                            sheet.write(row, col + 1,
                                                        account['amount'],
                                                        txt_name)
                                            col += 1
                    index += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Total Liabilities',
                            side_heading_sub)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['total_liability'],
                                side_heading_sub)
                    col += 1
                col = 0
                row += 1
                sheet.write(row, col, 'EQUITY', sub_heading)
                sheet.write(row, col + 1, '', sub_heading)
                row += 1
                sheet.write(row, col, 'Unallocated Earnings', side_heading_sub)
                sheet.write(row, col + 1, ' ', side_heading_sub)
                row += 1
                sheet.write(row, col, 'Current Earnings', txt_name)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['total_earnings'],
                                txt_name)
                    col += 1
                col = 0
                row += 1
                sheet.write(row, col, 'Current Allocated Earnings',
                            txt_name_left)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['equity_unaffected'][1],
                                txt_name)
                    col += 1
                index = 0
                for datas in data['datas']:
                    if index == 0:
                        for accounts in datas['equity_unaffected'][0]:
                            account_name = accounts['name']
                            account_value = 0
                            for datas in data['datas']:
                                for account in datas['equity_unaffected'][
                                    0]:
                                    if account_name == account['name'] and \
                                            account['amount'] != '0.00':
                                        account_value = 1
                            if account_value == 1:
                                row += 1
                                col = 0
                                sheet.write(row, col, accounts['name'],
                                            txt_name)
                                for datas in data['datas']:
                                    for account in \
                                            datas['equity_unaffected'][
                                                0]:
                                        if account_name == account['name']:
                                            sheet.write(row, col + 1,
                                                        account['amount'],
                                                        txt_name)
                                            col += 1
                    index += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Total Unallocated Earnings',
                            side_heading_sub)
                for datas in data['datas']:
                    sheet.write(row, col + 1,
                                datas['total_unallocated_earning'],
                                side_heading_sub)
                    col += 1
                col = 0
                row += 1
                sheet.write(row, col, 'Retained Earnings', txt_name_left)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['equity'][1],
                                txt_name)
                    col += 1
                index = 0
                for datas in data['datas']:
                    if index == 0:
                        for accounts in datas['equity'][0]:
                            account_name = accounts['name']
                            account_value = 0
                            for datas in data['datas']:
                                for account in datas['equity'][
                                    0]:
                                    if account_name == account['name'] and \
                                            account['amount'] != '0.00':
                                        account_value = 1
                            if account_value == 1:
                                row += 1
                                col = 0
                                sheet.write(row, col, accounts['name'],
                                            txt_name)
                                for datas in data['datas']:
                                    for account in datas['equity'][0]:
                                        if account_name == account['name']:
                                            sheet.write(row, col + 1,
                                                        account['amount'],
                                                        txt_name)
                                            col += 1
                    index += 1
                row += 1
                col = 0
                sheet.write(row, col, 'Total EQUITY', side_heading_sub)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['total_equity'],
                                side_heading_sub)
                    col += 1
                col = 0
                row += 1
                sheet.write(row, col, 'LIABILITIES + EQUITY', side_heading_sub)
                for datas in data['datas']:
                    sheet.write(row, col + 1, datas['total_balance'],
                                side_heading_sub)
                    col += 1
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
