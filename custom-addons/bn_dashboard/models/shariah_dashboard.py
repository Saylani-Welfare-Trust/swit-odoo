# -*- coding: utf-8 -*-
from datetime import timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.osv import expression


class ShariahDashboard(models.TransientModel):
    _name = 'shariah.dashboard'
    _description = 'Shariah Law Dashboard'

    @api.model
    def get_dashboard_data(self, date_from=False, date_to=False, analytic_id=False):
        Law = self.env['shariah.law']
        Transfer = self.env['shariah.transfer']

        # ---- Domains ----
        date_domain = []
        if date_from:
            date_domain.append(('date', '>=', date_from))
        if date_to:
            date_domain.append(('date', '<=', date_to))

        loc_domain = []
        if analytic_id:
            loc_domain.append(('analytic_account_id', 'child_of', analytic_id))

        base = date_domain + loc_domain

        # ---- Total Closing Balance (Latest record per account in range) ----
        records = Law.search(base)
        accounts = records.mapped('analytic_account_id')
        total_closing = 0.0
        for acc in accounts:
            latest = Law.search([('analytic_account_id', '=', acc.id)] + date_domain, order='date desc', limit=1)
            if latest:
                total_closing += latest.closing_balance

        # ---- Inflows & Outflows (For KPIs & Charts) ----
        pos = sum(records.mapped('pos_donation_amount'))
        api = sum(records.mapped('api_donation_amount'))
        dik = sum(records.mapped('dik_amount'))
        
        # Outflows are stored as negative values in the model, we use abs() for visual clarity
        po = abs(sum(records.mapped('po_amount')))
        welfare = abs(sum(records.mapped('welfare_amount')))
        micro = abs(sum(records.mapped('microfinance_amount')))
        expense = abs(sum(records.mapped('expense_amount')))

        # Transfers can be in or out depending on the segment
        transfers = Transfer.search(loc_domain + [('state', '=', 'posted')])
        if analytic_id:
            transfer_in = sum(transfers.filtered(lambda t: t.destination_analytic_account_id.id == analytic_id).mapped('amount'))
            transfer_out = sum(transfers.filtered(lambda t: t.source_analytic_account_id.id == analytic_id).mapped('amount'))
        else:
            transfer_in = sum(transfers.mapped('amount'))
            transfer_out = sum(transfers.mapped('amount'))

        total_inflow = pos + api + dik + transfer_in
        total_outflow = po + welfare + micro + expense + transfer_out

        # ---- Trend (Last 12 Months) ----
        today = fields.Date.context_today(self)
        first_this_month = today.replace(day=1)
        trend = []
        for i in range(11, -1, -1):
            m_start = first_this_month - relativedelta(months=i)
            m_end = m_start + relativedelta(months=1) - timedelta(days=1)
            
            m_domain = [
                ('date', '>=', str(m_start)),
                ('date', '<=', str(m_end)),
            ] + loc_domain
                
            m_records = Law.search(m_domain)
            m_in = sum(m_records.mapped('pos_donation_amount')) + sum(m_records.mapped('api_donation_amount')) + sum(m_records.mapped('dik_amount'))
            m_out = abs(sum(m_records.mapped('po_amount')) + sum(m_records.mapped('welfare_amount')) + sum(m_records.mapped('microfinance_amount')) + sum(m_records.mapped('expense_amount')))
            
            trend.append({
                'label': m_start.strftime('%b %y'),
                'inflow': m_in,
                'outflow': m_out,
            })

        # ---- Segment Breakdown Table ----
        segments_data = []
        for acc in accounts:
            latest = Law.search([('analytic_account_id', '=', acc.id)] + date_domain, order='date desc', limit=1)
            if not latest:
                continue
            
            acc_records = records.filtered(lambda r: r.analytic_account_id.id == acc.id)
            acc_in = sum(acc_records.mapped('pos_donation_amount')) + sum(acc_records.mapped('api_donation_amount')) + sum(acc_records.mapped('dik_amount'))
            acc_out = abs(sum(acc_records.mapped('po_amount')) + sum(acc_records.mapped('welfare_amount')) + sum(acc_records.mapped('microfinance_amount')) + sum(acc_records.mapped('expense_amount')))
            
            segments_data.append({
                'name': acc.name,
                'inflow': acc_in,
                'outflow': acc_out,
                'closing_balance': latest.closing_balance,
            })
        segments_data = sorted(segments_data, key=lambda x: x['closing_balance'], reverse=True)

        # ---- Recent Transfers ----
        recent_transfers = [{
            'date': t.date,
            'source': t.source_analytic_account_id.name,
            'destination': t.destination_analytic_account_id.name,
            'amount': t.amount,
        } for t in transfers[:10]]

        return {
            'kpis': {
                'total_closing': total_closing,
                'total_inflow': total_inflow,
                'total_outflow': total_outflow,
            },
            'inflows': [
                {'label': 'POS', 'amount': pos, 'color': '#007bff'},
                {'label': 'API / Wallet', 'amount': api, 'color': '#6f42c1'},
                {'label': 'DIK', 'amount': dik, 'color': '#20c997'},
                {'label': 'Transfers In', 'amount': transfer_in, 'color': '#17a2b8'},
            ],
            'outflows': [
                {'label': 'Purchase Orders', 'amount': po, 'color': '#dc3545'},
                {'label': 'Welfare', 'amount': welfare, 'color': '#fd7e14'},
                {'label': 'Microfinance', 'amount': micro, 'color': '#ffc107'},
                {'label': 'Expenses', 'amount': expense, 'color': '#6c757d'},
                {'label': 'Transfers Out', 'amount': transfer_out, 'color': '#343a40'},
            ],
            'trend': trend,
            'segments': segments_data,
            'recent_transfers': recent_transfers,
        }