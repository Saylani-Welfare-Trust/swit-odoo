import io
import json
import datetime
import xlsxwriter
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.date_utils import get_month, get_fiscal_year, get_quarter, \
    subtract

class ProfitLossReport(models.TransientModel):
    _inherit = 'dynamic.balance.sheet.report'

    analytic_plan_ids = fields.Many2many('account.analytic.plan', string='Analytic Plans')

    def filter(self, vals):
        # print(self.analytic_plan_ids, 'self.analytical_plan_ids')
        # print(vals, 'vals')
        """
            Update the filter criteria based on the provided values.
            :param vals: A dictionary containing the filter values to update.
            :return: The updated record.
            """
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
                self.update({'journal_ids': [(3, int(vals['journal_ids']))]})
            else:
                self.write({'journal_ids': [(4, int(vals['journal_ids']))]})
            filter.append({'journal_ids': self.journal_ids.mapped('code')})
        if 'account_ids' in vals:
            if int(vals['account_ids']) in self.account_ids.mapped('id'):
                self.update(
                    {'account_ids': [(3, int(vals['account_ids']))]})
            else:
                self.write({'account_ids': [(4, int(vals['account_ids']))]})
            filter.append({'account_ids': self.account_ids.mapped('name')})
        if 'analytic_plan_ids' in vals:
            if int(vals['analytic_plan_ids']) in self.analytic_plan_ids.mapped('id'):
                self.update(
                    {'analytic_plan_ids': [(3, int(vals['analytic_plan_ids']))]})
            else:
                self.write({'analytic_plan_ids': [(4, int(vals['analytic_plan_ids']))]})
            filter.append({'analytic_plan_ids': self.analytic_plan_ids.mapped('name')})
        if 'analytic_sub_plan_ids' in vals:
            if int(vals['analytic_sub_plan_ids']) in self.analytic_plan_ids.mapped('id'):
                self.update(
                    {'analytic_plan_ids': [(3, int(vals['analytic_sub_plan_ids']))]})
            else:
                self.write({'analytic_plan_ids': [(4, int(vals['analytic_sub_plan_ids']))]})
            filter.append({'analytic_sub_plan_ids': self.analytic_plan_ids.mapped('name')})
        if 'analytic_ids' in vals:
            if int(vals['analytic_ids']) in self.analytic_ids.mapped('id'):
                self.update(
                    {'analytic_ids': [(3, int(vals['analytic_ids']))]})
            else:
                self.write({'analytic_ids': [(4, int(vals['analytic_ids']))]})
            filter.append({'analytic_ids': self.analytic_ids.mapped('name')})
        if 'target' in vals:
            self.write({'target_move': vals['target']})
            filter.append({'target_move': self.target_move})

        return filter


    def _get_filter_data(self, selected_analytic_plan_ids):
        """
            Retrieve the filter data for journals and accounts.

            :return: A dictionary containing the filter data.
            """
        journal_ids = self.env['account.journal'].search([])
        journal = [{'id': journal.id, 'name': journal.name} for journal in
                   journal_ids]

        account_ids = self.env['account.account'].search([])
        account = [{'id': account.id, 'name': account.name} for account in
                   account_ids]

        analytic_plan_ids = self.env['account.analytic.plan'].search([
            ('parent_id', '=', False)
        ])
        analytic_plan = [{'id': analytic_plan.id, 'name': analytic_plan.name} for analytic_plan in analytic_plan_ids]

        analytic_sub_plan_ids = self.env['account.analytic.plan'].search([
            ('parent_id', 'in', selected_analytic_plan_ids)
        ])
        analytic_sub_plan = [{'id': analytic_sub_plan.id, 'name': analytic_sub_plan.name} for analytic_sub_plan in analytic_sub_plan_ids]


        analytic_ids = self.env['account.analytic.account'].search([
            ('plan_id', 'in', selected_analytic_plan_ids)
        ])
        analytic = [{'id': analytic.id, 'name': analytic.name} for analytic in
                    analytic_ids]

        filter = {
            'journal': journal,
            'account': account,
            'analytic_plan': analytic_plan,
            'analytic_sub_plan': analytic_sub_plan,
            'analytic': analytic
        }
        return filter

    def get_analytic_plan_ids(self):
        return self.analytic_plan_ids.ids

    @api.model
    def view_report(self, option, comparison, comparison_type, selected_analytic_plan_ids):
        datas = []
        account_types = {
            'income': 'income',
            'income_other': 'income_other',
            'expense': 'expense',
            'expense_depreciation': 'expense_depreciation',
            'expense_direct_cost': 'expense_direct_cost',
            'asset_receivable': 'asset_receivable',
            'asset_cash': 'asset_cash',
            'asset_current': 'asset_current',
            'asset_non_current': 'asset_non_current',
            'asset_prepayments': 'asset_prepayments',
            'asset_fixed': 'asset_fixed',
            'liability_payable': 'liability_payable',
            'liability_credit_card': 'liability_credit_card',
            'liability_current': 'liability_current',
            'liability_non_current': 'liability_non_current',
            'equity': 'equity',
            'equity_unaffected': 'equity_unaffected',
        }
        financial_report_id = self.browse(option)
        current_year = fields.Date.today().year
        current_date = fields.Date.today()
        if financial_report_id.target_move == 'draft':
            target_move = ['posted', 'draft']
        else:
            target_move = ['posted']
        if comparison:
            for count in range(0, int(comparison) + 1):
                if comparison_type == "month":
                    account_move_lines = self.env['account.move.line'].search(
                        [(
                            'parent_state', 'in', target_move),
                            ('date', '>=', (current_date - datetime.timedelta(
                                days=30 * count)).strftime('%Y-%m-01')),
                            ('date', '<=', (current_date - datetime.timedelta(
                                days=30 * count)).strftime('%Y-%m-12'))])
                elif comparison_type == "year":
                    account_move_lines = self.env['account.move.line'].search(
                        [(
                            'parent_state', 'in', target_move),
                            ('date', '>=', f'{current_year - count}-01-01'),
                            ('date', '<=', f'{current_year - count}-12-31')])
                lists = [{'id': rec.id, 'value': [eval(i) for i in
                                                  rec.analytic_distribution.keys()]}
                         for rec in account_move_lines if
                         rec.analytic_distribution]
                if financial_report_id.analytic_ids:
                    account_move_lines = account_move_lines.filtered(lambda
                                                                         rec: rec.id in [
                        lst['id'] for lst in lists if lst['value'] and any(
                            i in financial_report_id.analytic_ids.mapped('id')
                            for i in lst['value'])])
                account_move_lines = account_move_lines.filtered(lambda
                                                                     a: not financial_report_id.journal_ids or a.journal_id in financial_report_id.journal_ids)
                account_move_lines = account_move_lines.filtered(lambda
                                                                     a: not financial_report_id.account_ids or a.account_id in financial_report_id.account_ids)
                account_move_lines = account_move_lines.filtered(lambda
                                                                     a: not financial_report_id.date_from or a.date >= financial_report_id.date_from)
                account_move_lines = account_move_lines.filtered(lambda
                                                                     a: not financial_report_id.date_to or a.date <= financial_report_id.date_to)
                account_entries = {}
                for account_type in account_types.values():
                    account_entries[account_type] = self._get_entries(
                        account_move_lines, self.env['account.account'].search(
                            [('account_type', '=', account_type)]),
                        account_type)
                total_income = sum(
                    float(entry['amount'].replace(',', '')) for account_type
                    in
                    ['income', 'income_other'] for entry in
                    account_entries[account_type][0]) - sum(
                    float(entry['amount'].replace(',', '')) for entry in
                    account_entries['expense_direct_cost'][0])
                total_expense = sum(
                    float(entry['amount'].replace(',', '')) for account_type
                    in
                    ['expense', 'expense_depreciation'] for entry in
                    account_entries[account_type][0])
                total_current_asset = sum(
                    float(entry['amount'].replace(',', '')) for account_type
                    in
                    ['asset_receivable', 'asset_current', 'asset_cash',
                     'asset_prepayments'] for entry in
                    account_entries[account_type][0])
                total_assets = total_current_asset + sum(
                    float(entry['amount'].replace(',', '')) for account_type
                    in
                    ['asset_fixed', 'asset_non_current'] for entry in
                    account_entries[account_type][0])
                total_current_liability = sum(
                    float(entry['amount'].replace(',', '')) for account_type
                    in
                    ['liability_current', 'liability_payable'] for entry in
                    account_entries[account_type][0])
                total_liability = total_current_liability + sum(
                    float(entry['amount'].replace(',', '')) for account_type
                    in
                    ['liability_non_current'] for entry in
                    account_entries[account_type][0])
                total_unallocated_earning = (
                                                    total_income - total_expense) + sum(
                    float(entry['amount'].replace(',', '')) for account_type
                    in
                    ['equity_unaffected'] for entry in
                    account_entries[account_type][0])
                total_equity = total_unallocated_earning + sum(
                    float(entry['amount'].replace(',', '')) for account_type
                    in
                    ['equity'] for entry in
                    account_entries[account_type][0])
                total = total_liability + total_equity
                data = {
                    'total': total_income - total_expense,
                    'total_expense': "{:,.2f}".format(total_expense),
                    'total_income': "{:,.2f}".format(total_income),
                    'total_current_asset': "{:,.2f}".format(
                        total_current_asset),
                    'total_assets': "{:,.2f}".format(total_assets),
                    'total_current_liability': "{:,.2f}".format(
                        total_current_liability),
                    'total_liability': "{:,.2f}".format(total_liability),
                    'total_earnings': "{:,.2f}".format(
                        total_income - total_expense),
                    'total_unallocated_earning': "{:,.2f}".format(
                        total_unallocated_earning),
                    'total_equity': "{:,.2f}".format(total_equity),
                    'total_balance': "{:,.2f}".format(total),
                    **account_entries}
                datas.append(data)
        else:
            account_move_lines = self.env['account.move.line'].search(
                [('parent_state', 'in', target_move),
                 ('date', '>=', f'{current_year}-01-01'),
                 ('date', '<=', f'{current_year}-12-31')])
            lists = [{'id': rec.id,
                      'value': [eval(i) for i in
                                rec.analytic_distribution.keys()]}
                     for rec in account_move_lines if
                     rec.analytic_distribution]
            if financial_report_id.analytic_ids:
                account_move_lines = account_move_lines.filtered(
                    lambda rec: rec.id in [lst['id'] for lst in lists if
                                           lst['value'] and any(
                                               i in financial_report_id.analytic_ids.mapped(
                                                   'id') for i in
                                               lst['value'])])
            account_move_lines = account_move_lines.filtered(lambda
                                                                 a: not financial_report_id.journal_ids or a.journal_id in financial_report_id.journal_ids)
            account_move_lines = account_move_lines.filtered(lambda
                                                                 a: not financial_report_id.account_ids or a.account_id in financial_report_id.account_ids)
            account_move_lines = account_move_lines.filtered(lambda
                                                                 a: not financial_report_id.date_from or a.date >= financial_report_id.date_from)
            account_move_lines = account_move_lines.filtered(lambda
                                                                 a: not financial_report_id.date_to or a.date <= financial_report_id.date_to)
            account_entries = {}
            for account_type in account_types.values():
                account_entries[account_type] = self._get_entries(
                    account_move_lines, self.env['account.account'].search(
                        [('account_type', '=', account_type)]), account_type)
            total_income = sum(
                float(entry['amount'].replace(',', '')) for account_type in
                ['income', 'income_other'] for entry in
                account_entries[account_type][0]) - sum(
                float(entry['amount'].replace(',', '')) for entry in
                account_entries['expense_direct_cost'][0])
            total_expense = sum(
                float(entry['amount'].replace(',', '')) for account_type in
                ['expense', 'expense_depreciation'] for entry in
                account_entries[account_type][0])
            total_current_asset = sum(
                float(entry['amount'].replace(',', '')) for account_type in
                ['asset_receivable', 'asset_current', 'asset_cash',
                 'asset_prepayments'] for entry in
                account_entries[account_type][0])
            total_assets = total_current_asset + sum(
                float(entry['amount'].replace(',', '')) for account_type in
                ['asset_fixed', 'asset_non_current'] for entry in
                account_entries[account_type][0])
            total_current_liability = sum(
                float(entry['amount'].replace(',', '')) for account_type in
                ['liability_current', 'liability_payable'] for entry in
                account_entries[account_type][0])
            total_liability = total_current_liability + sum(
                float(entry['amount'].replace(',', '')) for account_type in
                ['liability_non_current'] for entry in
                account_entries[account_type][0])
            total_unallocated_earning = (total_income - total_expense) + sum(
                float(entry['amount'].replace(',', '')) for account_type in
                ['equity_unaffected'] for entry in
                account_entries[account_type][0])
            total_equity = total_unallocated_earning + sum(
                float(entry['amount'].replace(',', '')) for account_type in
                ['equity'] for entry in account_entries[account_type][0])
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
                'total_earnings': "{:,.2f}".format(
                    total_income - total_expense),
                'total_unallocated_earning': "{:,.2f}".format(
                    total_unallocated_earning),
                'total_equity': "{:,.2f}".format(total_equity),
                'total_balance': "{:,.2f}".format(total),
                **account_entries}
            datas.append(data)
        filters = self._get_filter_data(selected_analytic_plan_ids)
        return data, filters, datas
