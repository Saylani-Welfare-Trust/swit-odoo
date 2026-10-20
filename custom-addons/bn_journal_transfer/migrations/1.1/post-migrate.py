# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    One-time data migration:
    Split existing 'descripiton' into session / category / deposit_slip_no.
    Idempotent — safe to re-run.
    """
    if not version:
        return  # fresh install, nothing to migrate

    _logger.info("journal.transfer: starting description split migration...")

    cr.execute("""
        SELECT COUNT(*) FROM journal_transfer
        WHERE descripiton IS NOT NULL
          AND descripiton <> ''
          AND session IS NULL
    """)
    pending = cr.fetchone()[0]
    _logger.info("journal.transfer: %s records to migrate", pending)

    if not pending:
        _logger.info("journal.transfer: nothing to do, skipping.")
        return

    cr.execute("""
        UPDATE journal_transfer
        SET
            session         = NULLIF(TRIM(SPLIT_PART(descripiton, ' - ', 1)), ''),
            category        = NULLIF(TRIM(SPLIT_PART(descripiton, ' - ', 2)), ''),
            deposit_slip_no = NULLIF(TRIM(SPLIT_PART(descripiton, ' - ', 3)), '')
        WHERE descripiton IS NOT NULL
          AND descripiton <> ''
          AND session IS NULL
    """)
    _logger.info(
        "journal.transfer: migration done. Rows affected: %s", cr.rowcount
    )