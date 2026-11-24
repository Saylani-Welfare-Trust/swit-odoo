# -*- coding: utf-8 -*-
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

SHARIAH_GROUP = 'bn_dashboard.group_shariah_dashboard_user'
INFLOW_FIELDS = ('pos_donation_amount', 'api_donation_amount', 'dik_amount')
# outflows are stored as negative amounts
OUTFLOW_FIELDS = ('po_amount', 'welfare_amount', 'microfinance_amount', 'expense_amount')


class ShariahDashboard(models.AbstractModel):
    """Figures of the Shariah Law Dashboard (no records of its own)."""
    _name = 'shariah.dashboard'
    _description = 'Shariah Law Dashboard'

    @api.model
    def _check_access(self):
        if not (self.env.su or self.env.user.has_group(SHARIAH_GROUP) or self.env.user.has_group('base.group_system')):
            raise AccessError(_("You are not allowed to see the Shariah Law Dashboard."))

    @api.model
    def _allowed_segments(self):
        """The segments the user may see (Users > Shariah Dashboard Segments, with
        everything under them); False = every segment."""
        allowed = self.env.user.sudo().shariah_analytic_ids
        if not allowed:
            return False
        return self.env['account.analytic.account'].sudo().search([('id', 'child_of', allowed.ids)])

    @api.model
    def get_segments(self):
        """The segments offered in the dashboard's filter: those with Shariah Law
        figures, limited to the user's allowed segments."""
        self._check_access()
        accounts = self.env['shariah.law'].sudo()._read_group([], ['analytic_account_id'])
        accounts = self.env['account.analytic.account'].sudo().browse(
            [account.id for account, in accounts if account]).sorted('name')
        allowed = self._allowed_segments()
        if allowed is not False:
            accounts &= allowed
        return [{'id': account.id, 'name': account.display_name} for account in accounts]

    @api.model
    def get_dashboard_data(self, date_from=False, date_to=False, analytic_id=False):
        """Inflows, outflows, transfers and closing balances of the period, for one
        segment (with the segments under it) or all the user's segments. The
        figures are read as superuser, so the dashboard group and the user's
        segments are checked here."""
        self._check_access()
        Law = self.env['shariah.law'].sudo()
        Transfer = self.env['shariah.transfer'].sudo()
        Account = self.env['account.analytic.account'].sudo()

        today = fields.Date.context_today(self)
        date_from = fields.Date.to_date(date_from) or False
        date_to = fields.Date.to_date(date_to) or False

        # ---- segments in scope ----
        allowed = self._allowed_segments()
        if analytic_id:
            segments = Account.search([('id', 'child_of', int(analytic_id))])
            if allowed is not False:
                if int(analytic_id) not in allowed.ids:
                    raise AccessError(_("You are not allowed to see this segment."))
                segments &= allowed
        else:
            segments = allowed  # False: every segment

        segment_domain = [('analytic_account_id', 'in', segments.ids)] if segments is not False else []
        date_domain = ([('date', '>=', date_from)] if date_from else []) + ([('date', '<=', date_to)] if date_to else [])
        domain = segment_domain + date_domain

        # ---- inflows and outflows of the period ----
        aggregates = ['%s:sum' % name for name in INFLOW_FIELDS + OUTFLOW_FIELDS]
        totals = dict(zip(INFLOW_FIELDS + OUTFLOW_FIELDS, Law._read_group(domain, [], aggregates)[0]))
        totals = {name: value or 0.0 for name, value in totals.items()}
        pos, api_amount, dik = (totals[name] for name in INFLOW_FIELDS)
        po, welfare, micro, expense = (abs(totals[name]) for name in OUTFLOW_FIELDS)

        # ---- transfers of the period ----
        transfer_domain = [('state', '=', 'posted')] + date_domain
        if segments is not False:
            transfer_domain += ['|', ('source_analytic_account_id', 'in', segments.ids),
                                ('destination_analytic_account_id', 'in', segments.ids)]
        transfers = Transfer.search(transfer_domain)
        if segments is not False:
            # only what crosses the edge of the segments in scope: a move inside them is neither in nor out
            transfer_in = sum(transfers.filtered(
                lambda t: t.destination_analytic_account_id in segments
                and t.source_analytic_account_id not in segments).mapped('amount'))
            transfer_out = sum(transfers.filtered(
                lambda t: t.source_analytic_account_id in segments
                and t.destination_analytic_account_id not in segments).mapped('amount'))
        else:
            # between segments of the trust: they move money, they bring none in or out
            transfer_in = transfer_out = 0.0

        # ---- closing balance: the last figure of each segment up to the end of the period ----
        # (one row per segment, in the database: the daily figures can be many)
        Law.flush_model(['analytic_account_id', 'date', 'closing_balance'])
        where, params = ['analytic_account_id IS NOT NULL'], []
        if segments is not False:
            where.append('analytic_account_id = ANY(%s)')
            params.append(segments.ids or [0])
        if date_to:
            where.append('date <= %s')
            params.append(date_to)
        self.env.cr.execute("""
            SELECT DISTINCT ON (analytic_account_id) analytic_account_id, closing_balance
              FROM shariah_law
             WHERE %s
          ORDER BY analytic_account_id, date DESC, id DESC
        """ % ' AND '.join(where), params)
        latest = {Account.browse(account_id): balance or 0.0 for account_id, balance in self.env.cr.fetchall()}
        total_closing = sum(latest.values())

        # ---- trend: last 12 months ----
        first_this_month = today.replace(day=1)
        start = first_this_month - relativedelta(months=11)
        monthly = Law._read_group(segment_domain + [('date', '>=', start), ('date', '<=', today)],
                                  ['date:month'], aggregates)
        by_month = {month: values for month, *values in monthly}
        trend = []
        for i in range(12):
            month = start + relativedelta(months=i)
            values = dict(zip(INFLOW_FIELDS + OUTFLOW_FIELDS, by_month.get(month) or [0.0] * len(aggregates)))
            trend.append({
                'label': month.strftime('%b %y'),
                'inflow': sum(values[name] or 0.0 for name in INFLOW_FIELDS),
                'outflow': abs(sum(values[name] or 0.0 for name in OUTFLOW_FIELDS)),
            })

        # ---- by segment ----
        per_segment = Law._read_group(domain, ['analytic_account_id'], aggregates)
        flows = {account: values for account, *values in per_segment}
        segments_data = []
        for account in set(flows) | set(latest):
            values = dict(zip(INFLOW_FIELDS + OUTFLOW_FIELDS, flows.get(account) or [0.0] * len(aggregates)))
            segments_data.append({
                'id': account.id,
                'name': account.display_name,
                'inflow': sum(values[name] or 0.0 for name in INFLOW_FIELDS),
                'outflow': abs(sum(values[name] or 0.0 for name in OUTFLOW_FIELDS)),
                'closing_balance': latest.get(account, 0.0),
            })
        segments_data.sort(key=lambda item: item['closing_balance'], reverse=True)

        return {
            'kpis': {
                'total_closing': total_closing,
                'total_inflow': pos + api_amount + dik + transfer_in,
                'total_outflow': po + welfare + micro + expense + transfer_out,
            },
            'inflows': [
                {'label': _('POS'), 'amount': pos, 'color': '#007bff'},
                {'label': _('API / Wallet'), 'amount': api_amount, 'color': '#6f42c1'},
                {'label': _('DIK'), 'amount': dik, 'color': '#20c997'},
                {'label': _('Transfers In'), 'amount': transfer_in, 'color': '#17a2b8'},
            ],
            'outflows': [
                {'label': _('Purchase Orders'), 'amount': po, 'color': '#dc3545'},
                {'label': _('Welfare'), 'amount': welfare, 'color': '#fd7e14'},
                {'label': _('Microfinance'), 'amount': micro, 'color': '#ffc107'},
                {'label': _('Expenses'), 'amount': expense, 'color': '#6c757d'},
                {'label': _('Transfers Out'), 'amount': transfer_out, 'color': '#343a40'},
            ],
            'trend': trend,
            'segments': segments_data,
            'recent_transfers': [{
                'id': t.id,
                'date': fields.Date.to_string(t.date),
                'source': t.source_analytic_account_id.display_name,
                'destination': t.destination_analytic_account_id.display_name,
                'amount': t.amount,
            } for t in transfers[:10]],
        }
