from odoo import models, api


class AccountGeneralLedger(models.TransientModel):
    _inherit = 'account.general.ledger'

    @api.model
    def get_filter_values(self, journal_ids, date_range, options,
                          analytic_ids, method,
                          advance_donation_only=False):
        """
        Extend the standard GL query.

        When ``advance_donation_only`` is True, we keep only those journal
        entries (``account.move``) that contain at least one line whose
        product is flagged ``is_advance_donation = True``.  Everything else
        is delegated to the parent implementation so date range, journals,
        options, analytics, opening balance, currency and running balance
        all keep behaving exactly like the standard GL.
        """
        # 1) Ask the parent for the un-filtered result
        result = super().get_filter_values(
            journal_ids, date_range, options, analytic_ids, method
        )

        # 2) Fast exit – caller does not want the special filter
        if not advance_donation_only:
            return result

        # 3) Collect every account.move.id that touches an advance-donation product
        self.env.cr.execute("""
            SELECT DISTINCT aml.move_id
              FROM account_move_line aml
              JOIN product_product  pp ON pp.id = aml.product_id
              JOIN product_template pt ON pt.id = pp.product_tmpl_id
             WHERE pt.is_advance_donation IS TRUE
               AND aml.move_id IS NOT NULL
        """)
        allowed_move_ids = {row[0] for row in self.env.cr.fetchall()}

        # 4) No matches → return an empty but well-shaped payload
        if not allowed_move_ids:
            return {
                'account_totals': {},
                'journal_ids':  result.get('journal_ids',  []) if isinstance(result, dict) else [],
                'analytic_ids': result.get('analytic_ids', []) if isinstance(result, dict) else [],
            }

        # 5) Snapshot the parent's account_totals before we mutate the dict
        original_totals = {}
        if isinstance(result, dict):
            original_totals = result.get('account_totals', {}) or {}

        # 6) Filter the per-account line lists
        filtered = {}
        for key, value in (result or {}).items():
            if key in ('journal_ids', 'analytic_ids'):
                filtered[key] = value
                continue
            if key == 'account_totals':
                continue
            if isinstance(value, list):
                kept = [
                    line for line in value
                    if isinstance(line, dict)
                       and line.get('move_id')
                       and line['move_id'][0] in allowed_move_ids
                ]
                if kept:
                    filtered[key] = kept
            else:
                filtered[key] = value

        # 7) Rebuild account_totals so the collapsed summary on screen
        #    matches exactly what is expanded underneath it.
        new_totals = {}
        for account, lines in filtered.items():
            if not isinstance(lines, list) or not lines:
                continue
            old = original_totals.get(account, {}) if isinstance(original_totals, dict) else {}
            total_debit  = sum(float(l.get('debit')  or 0.0) for l in lines)
            total_credit = sum(float(l.get('credit') or 0.0) for l in lines)
            new_totals[account] = {
                'currency_id':     old.get('currency_id', ''),
                'account_code':    old.get('account_code', ''),
                'account_name':    old.get('account_name', ''),
                'opening_balance': old.get('opening_balance', 0.0),
                'total_debit':     total_debit,
                'total_credit':    total_credit,
            }

        filtered['account_totals'] = new_totals
        return filtered