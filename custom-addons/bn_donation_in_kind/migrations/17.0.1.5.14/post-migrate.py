import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """The Unit of Measure of a Donation In Kind and of its lines is now the
    product's own unit. Records saved before were left without one: fill them."""
    if not version:
        return
    for table in ('donation_in_kind', 'donation_in_kind_line'):
        cr.execute(f"""
            UPDATE {table} AS rec
               SET product_uom_id = pt.uom_id
              FROM product_product pp
              JOIN product_template pt ON pt.id = pp.product_tmpl_id
             WHERE pp.id = rec.product_id
               AND rec.product_uom_id IS DISTINCT FROM pt.uom_id
        """)
        _logger.info("%s: Unit of Measure set from the product on %s records", table, cr.rowcount)
