import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE sadqa_jariya
           SET institution_category = institution_type
         WHERE institution_category IN ('construction', 'flood')
    """)
    _logger.info(
        "bn_sadqa_e_jariya: moved %s legacy Construction/Flood applications to their institution type",
        cr.rowcount,
    )
