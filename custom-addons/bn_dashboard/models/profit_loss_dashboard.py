from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

INCOME_TYPES = ('income', 'income_other')
EXPENSE_TYPES = ('expense', 'expense_direct_cost', 'expense_depreciation')
PL_GROUP = 'bn_dashboard.group_profit_loss_dashboard_user'


class ProfitLossDashboard(models.AbstractModel):
    """Figures of the Profit & Loss Dashboard (no records of its own)."""
    _name = 'profit.loss.dashboard'
    _description = 'Profit and Loss Dashboard'

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None):
        """Income, expenses and their monthly trend of the posted entries of the
        user's selected companies. The ledger is read as superuser (dashboard users
        need no Accounting rights), so the dashboard group is checked first."""
        if not (self.env.su or self.env.user.has_group(PL_GROUP) or self.env.user.has_group('base.group_system')):
            raise AccessError(_("You are not allowed to see the Profit & Loss Dashboard."))

        today = fields.Date.context_today(self)
        date_from = fields.Date.to_date(date_from) or date(today.year, 1, 1)
        date_to = fields.Date.to_date(date_to) or today

        Line = self.env['account.move.line'].sudo()
        domain = [
            ('parent_state', '=', 'posted'),
            ('company_id', 'in', self.env.companies.ids),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]
        income_domain = domain + [('account_id.account_type', 'in', INCOME_TYPES)]
        expense_domain = domain + [('account_id.account_type', 'in', EXPENSE_TYPES)]

        total_income = -(Line._read_group(income_domain, [], ['balance:sum'])[0][0] or 0.0)
        expense_lines = Line._read_group(expense_domain, ['account_id'], ['balance:sum'])
        total_expense = sum(balance or 0.0 for _account, balance in expense_lines)

        # the 5 biggest expense accounts
        expense_breakdown = sorted(
            ({'name': account.display_name, 'amount': balance}
             for account, balance in expense_lines if balance and balance > 0),
            key=lambda item: item['amount'], reverse=True)[:5]

        # monthly trend, grouped in the database
        income_by_month = dict(Line._read_group(income_domain, ['date:month'], ['balance:sum']))
        expense_by_month = dict(Line._read_group(expense_domain, ['date:month'], ['balance:sum']))
        months = sorted(set(income_by_month) | set(expense_by_month))

        return {
            'total_income': total_income,
            'total_expense': total_expense,
            'net_profit': total_income - total_expense,
            'expense_breakdown': expense_breakdown,
            'trend_labels': [month.strftime('%b %Y') for month in months],
            'trend_income': [-(income_by_month.get(month) or 0.0) for month in months],
            'trend_expense': [expense_by_month.get(month) or 0.0 for month in months],
            'date_from': fields.Date.to_string(date_from),
            'date_to': fields.Date.to_string(date_to),
        }
