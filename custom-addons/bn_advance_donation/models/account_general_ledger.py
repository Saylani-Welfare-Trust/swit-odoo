from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class AccountGeneralLedger(models.TransientModel):
    _inherit = 'account.general.ledger'

    @api.model
    def get_filter_values(self, journal_ids, date_range, options,
                          analytic_ids, method,
                          advance_donation_only=False):
        """
        Advance-donation filter on top of the standard General Ledger.

        When ``advance_donation_only`` is true we keep only those GL lines
        whose ``move_name`` (a.k.a. "V.No") belongs to an account.move that
        is either:
            a) linked to an advance-donation product line, or
            b) a cheque-deposit / payment move whose ``ref`` or ``name``
               equals an advance.donation.receipt name.
        """
        advance_donation_only = bool(advance_donation_only)
        _logger.info("ADV DONATION GL | advance_donation_only=%s",
                     advance_donation_only)

        # 1) Ask the parent for the full result
        result = super().get_filter_values(
            journal_ids, date_range, options, analytic_ids, method
        )

        if not advance_donation_only:
            return result

        # 2) Collect the *names* of every account.move tied to advance donations
        self.env.cr.execute("""
            SELECT DISTINCT am.name
              FROM account_move am
             WHERE am.name IS NOT NULL
               AND (
                    am.id IN (
                        SELECT DISTINCT aml.move_id
                          FROM account_move_line aml
                          JOIN product_product  pp ON pp.id = aml.product_id
                          JOIN product_template pt ON pt.id = pp.product_tmpl_id
                         WHERE pt.is_advance_donation IS TRUE
                    )
                    OR am.ref  IN (SELECT name FROM advance_donation_receipt
                                   WHERE name IS NOT NULL)
                    OR am.name IN (SELECT name FROM advance_donation_receipt
                                   WHERE name IS NOT NULL)
               )
        """)
        allowed_move_names = {row[0] for row in self.env.cr.fetchall() if row[0]}

        _logger.info("ADV DONATION GL | %s matching account.move name(s)",
                     len(allowed_move_names))

        # 3) Shaped-empty payload if nothing matched
        j_ids = result.get('journal_ids',  []) if isinstance(result, dict) else []
        a_ids = result.get('analytic_ids', []) if isinstance(result, dict) else []
        if not allowed_move_names:
            return {
                'account_totals': {},
                'journal_ids':    j_ids,
                'analytic_ids':   a_ids,
            }

        # 4) Walk the parent payload and keep only matching lines
        old_totals = result.get('account_totals', {}) or {}

        filtered = {
            'account_totals': {},
            'journal_ids':    j_ids,
            'analytic_ids':   a_ids,
        }

        for key, value in result.items():
            if key in ('account_totals', 'journal_ids', 'analytic_ids'):
                continue
            if not isinstance(value, list):
                continue

            kept = [
                line for line in value
                if isinstance(line, dict) and line.get('move_name') in allowed_move_names
            ]
            if not kept:
                continue

            filtered[key] = kept

            old = old_totals.get(key, {}) or {}
            filtered['account_totals'][key] = {
                'currency_id':     old.get('currency_id', ''),
                'account_code':    old.get('account_code', ''),
                'account_name':    old.get('account_name', ''),
                'opening_balance': old.get('opening_balance', 0.0),
                'total_debit':     sum(float(l.get('debit')  or 0.0) for l in kept),
                'total_credit':    sum(float(l.get('credit') or 0.0) for l in kept),
            }

        return filtered