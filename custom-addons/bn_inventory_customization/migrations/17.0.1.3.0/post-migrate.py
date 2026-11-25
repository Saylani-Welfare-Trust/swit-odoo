import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _column(cr, table, column):
    cr.execute("""
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s
           AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    """Migrate legacy livestock weight configuration into livestock.variant.line."""

    required_columns = (
        ('product_template', 'purchase_product'),
        ('product_template', 'livestock_variant'),
        ('product_attribute_value', 'from_kg'),
        ('product_attribute_value', 'to_kg'),
    )

    if not all(_column(cr, *column) for column in required_columns):
        _logger.warning(
            "Livestock migration skipped: required legacy columns are missing."
        )
        return

    main_condition = (
        "AND (pt.main_attribute_id IS NULL "
        "OR pav.attribute_id = pt.main_attribute_id)"
        if _column(cr, 'product_template', 'main_attribute_id')
        else ""
    )

    cr.execute("""
        SELECT
            pt.livestock_variant,
            pt.purchase_product,
            pp.id,
            pav.from_kg,
            pav.to_kg
        FROM product_template pt
        JOIN product_product pp
            ON pp.product_tmpl_id = pt.id
           AND pp.active
        JOIN product_variant_combination pvc
            ON pvc.product_product_id = pp.id
        JOIN product_template_attribute_value ptav
            ON ptav.id = pvc.product_template_attribute_value_id
        JOIN product_attribute_value pav
            ON pav.id = ptav.product_attribute_value_id
        WHERE pt.purchase_product IS NOT NULL
          AND pt.livestock_variant IS NOT NULL
          AND pav.to_kg > pav.from_kg
          {main_condition}
        ORDER BY
            pt.livestock_variant,
            pt.purchase_product,
            pav.from_kg
    """.format(main_condition=main_condition))

    rows = cr.fetchall()

    env = api.Environment(cr, SUPERUSER_ID, {})
    Band = env['livestock.variant.line']
    Product = env['product.product']
    Template = env['product.template']

    created = skipped = 0

    for variant_id, purchase_id, product_id, from_kg, to_kg in rows:

        purchase = Product.browse(purchase_id).exists()
        configured_variant = Template.browse(variant_id).exists()

        if not purchase or not configured_variant:
            skipped += 1
            _logger.warning(
                "Livestock band skipped: invalid purchase product or "
                "livestock variant configuration. Purchase ID: %s, "
                "Variant ID: %s.",
                purchase_id, variant_id
            )
            continue

        if not purchase.check_stock:
            skipped += 1
            _logger.warning(
                "Livestock band skipped: %s is not configured as a "
                "livestock product (Is Livestock Product is disabled).",
                purchase.display_name
            )
            continue

        # Resolve the receiving product from the configured variant template.
        receiving_products = configured_variant.product_variant_ids.filtered(
            lambda product: product.active
        )

        if not receiving_products:
            skipped += 1
            _logger.warning(
                "Livestock band skipped: no active product variant found "
                "for template %s (ID: %s).",
                configured_variant.display_name,
                configured_variant.id
            )
            continue

        # The SQL product identifies the actual variant carrying the
        # weight attribute. Prefer it when it belongs to the configured
        # livestock variant template.
        receiving_product = receiving_products.filtered(
            lambda product: product.id == product_id
        )[:1]

        if not receiving_product:
            skipped += 1
            _logger.warning(
                "Livestock band skipped: product %s does not belong to "
                "configured livestock variant template %s.",
                product_id,
                configured_variant.display_name
            )
            continue

        if receiving_product == purchase:
            skipped += 1
            _logger.warning(
                "Livestock band skipped: purchase product and receiving "
                "variant are identical (%s). Check livestock configuration.",
                purchase.display_name
            )
            continue

        if Band.search_count([
            ('purchase_product_id', '=', purchase.id),
            ('from_kg', '<', to_kg),
            ('to_kg', '>', from_kg),
        ]):
            skipped += 1
            _logger.warning(
                "Livestock band %s-%s kg of product %s overlaps an "
                "existing band: not created.",
                from_kg, to_kg, purchase.display_name
            )
            continue

        Band.create({
            'purchase_product_id': purchase.id,
            'from_kg': from_kg,
            'to_kg': to_kg,
            'product_id': receiving_product.id,
        })

        created += 1

    _logger.info(
        "Livestock weight bands migration completed: "
        "%s created, %s skipped.",
        created, skipped
    )