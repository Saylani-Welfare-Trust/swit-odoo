# -*- coding: utf-8 -*-
"""Bills Finance confirmed before this version were never marked as forwarded
to Treasury (nothing set the flag): they are now, so they can still be paid.
Posted bills of a Purchase Order that Finance never confirmed must be
confirmed (Finance Confirm & Post) before they can be paid."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE account_move
           SET forwarded_to_treasury = TRUE,
               treasury_forwarded_by = finance_confirmed_by,
               treasury_forwarded_date = finance_confirmed_date
         WHERE move_type = 'in_invoice'
           AND finance_confirmed IS TRUE
           AND forwarded_to_treasury IS NOT TRUE
    """)
    _logger.info("Vendor bills marked as forwarded to Treasury: %s", cr.rowcount)
    cr.execute("""
        SELECT count(DISTINCT m.id)
          FROM account_move m
          JOIN account_move_line l ON l.move_id = m.id AND l.purchase_line_id IS NOT NULL
         WHERE m.move_type = 'in_invoice' AND m.state = 'posted'
           AND m.payment_state NOT IN ('paid', 'in_payment', 'reversed')
           AND m.finance_confirmed IS NOT TRUE
    """)
    _logger.info("Posted Purchase Order bills still to be confirmed by Finance before payment: %s",
                 cr.fetchone()[0])
