import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        SELECT res_id
          FROM ir_model_data
         WHERE module = 'bn_sadqa_e_jariya'
           AND name = 'disbursement_category_cash'
           AND model = 'sadqa.jariya.disbursement.category'
    """)
    row = cr.fetchone()
    if not row:
        return

    category_id = row[0]
    cr.execute(
        "UPDATE sadqa_jariya_disbursement_category SET name = 'Bank' WHERE id = %s",
        [category_id],
    )
    cr.execute("""
        UPDATE sadqa_jariya_line
           SET collection_point = 'bank'
         WHERE disbursement_category_id = %s
           AND collection_point = 'branch'
           AND state = 'draft'
    """, [category_id])
    one_time_count = cr.rowcount
    cr.execute("""
        UPDATE sadqa_jariya_recurring_line
           SET collection_point = 'bank'
         WHERE disbursement_category_id = %s
           AND collection_point = 'branch'
           AND state = 'draft'
    """, [category_id])
    _logger.info(
        "bn_sadqa_e_jariya: renamed Cash to Bank and routed %s one-time, %s recurring draft lines to Bank",
        one_time_count,
        cr.rowcount,
    )
