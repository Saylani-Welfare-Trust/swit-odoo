import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE sadqa_jariya
           SET state = CASE state
               WHEN 'committee_approval' THEN 'hod_approve'
               WHEN 'hod_approve' THEN 'committee_approval'
           END
         WHERE state IN ('committee_approval', 'hod_approve')
    """)
    _logger.info("bn_sadqa_e_jariya: reordered approval stage for %s in-progress applications", cr.rowcount)
