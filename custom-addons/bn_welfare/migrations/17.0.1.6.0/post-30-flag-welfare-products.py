# -*- coding: utf-8 -*-
"""Welfare lines now only take products flagged "Is Welfare". A database coming
from a Welfare that did not check it (pre_production) has lines on unflagged
products: flag the products already used by welfare lines so the same
products can still be used."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return  # fresh install
    cr.execute("""
        UPDATE product_template t SET is_welfare = TRUE
          FROM product_product p
         WHERE p.product_tmpl_id = t.id AND t.is_welfare IS NOT TRUE
           AND (p.id IN (SELECT product_id FROM welfare_line WHERE product_id IS NOT NULL)
                OR p.id IN (SELECT product_id FROM welfare_recurring_line WHERE product_id IS NOT NULL))
    """)
    flagged = cr.rowcount
    # product.product.is_welfare is stored (related): keep it in step
    cr.execute("""UPDATE product_product p SET is_welfare = t.is_welfare
                    FROM product_template t WHERE p.product_tmpl_id = t.id
                     AND p.is_welfare IS DISTINCT FROM t.is_welfare""")
    _logger.info("bn_welfare: %s product(s) used by welfare lines flagged Is Welfare", flagged)
