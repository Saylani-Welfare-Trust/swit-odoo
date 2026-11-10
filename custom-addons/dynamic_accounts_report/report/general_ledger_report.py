from odoo import api, models


class GeneralLedgerReport(models.AbstractModel):
    _name = 'report.dynamic_accounts_report.general_ledger'
    _description = 'General Ledger PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        report_options = data.get('report_options')
        if report_options is None:
            return data

        report_data = self.env['account.general.ledger'].get_filter_values(
            report_options.get('journal_ids') or [],
            report_options.get('date_range') or 'month',
            report_options.get('options') or {},
            report_options.get('analytic_ids') or [],
            report_options.get('method') or {'accrual': True},
            include_filter_values=False,
        )
        accounts = [
            key for key in report_data
            if key not in ('account_totals', 'journal_ids', 'analytic_ids')
        ]
        totals = report_data.get('account_totals') or {}
        total_debit = sum(value.get('total_debit', 0.0) for value in totals.values())
        total_credit = sum(value.get('total_credit', 0.0) for value in totals.values())
        currency = self.env.company.currency_id.symbol

        return {
            'doc_ids': docids,
            'doc_model': 'account.general.ledger',
            'account': accounts,
            'data': report_data,
            'total': totals,
            'filters': data.get('filters') or {},
            'grand_total': {
                'total_debit': total_debit,
                'total_credit': total_credit,
                'currency': currency,
            },
            'report_name': data.get('report_name') or 'General Ledger',
        }
