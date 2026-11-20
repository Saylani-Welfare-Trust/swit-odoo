# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

COLUMNS = ('num_of_children', 'num_of_sons', 'num_of_daughters')

# First number in the text ('2 sons' -> 2); no number, or one too long to be a count
# (e.g. a phone number typed in by mistake) -> empty
TO_INTEGER = r"""
    CASE WHEN substring({col} from '\d+') ~ '^\d{{1,6}}$'
         THEN substring({col} from '\d+')::int4
    END
"""


def migrate(cr, version):
    """
    One-time conversion of num_of_children / num_of_sons / num_of_daughters
    from Char to Integer. The ORM converts with a plain cast, which aborts the
    upgrade on any text such as '' or '2 sons', so convert here first.
    Idempotent — columns that are already integer are skipped.
    """
    if not version:
        return  # fresh install, nothing to migrate

    for col in COLUMNS:
        cr.execute("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'welfare' AND column_name = %s
        """, [col])
        row = cr.fetchone()
        if not row or row[0] == 'integer':
            continue

        expr = TO_INTEGER.format(col=col)
        cr.execute(f"""
            SELECT name, {col}, {expr} FROM welfare
            WHERE btrim({col}) !~ '^\\d{{1,6}}$' AND btrim({col}) <> ''
        """)
        for name, old, new in cr.fetchall():
            _logger.warning("welfare %s: %s %r is not a plain number, converted to %s", name, col, old, new)

        cr.execute(f"ALTER TABLE welfare ALTER COLUMN {col} TYPE int4 USING {expr}")
        _logger.info("welfare: %s converted to integer", col)
