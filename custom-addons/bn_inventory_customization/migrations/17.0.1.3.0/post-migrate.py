import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _column(cr, table, column):
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
               (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    """The weight bands were set on the products (Purchase Product, Livestock
    Variant, Main Attribute) and on the attribute values (From / To kg). They
    become the bands of the Livestock Variants: one per product variant of each
    configured template, with the weight range of its attribute value."""
    if not all(_column(cr, *c) for c in (('product_template', 'purchase_product'),
                                         ('product_template', 'livestock_variant'),
                                         ('product_attribute_value', 'from_kg'),
                                         ('product_attribute_value', 'to_kg'))):
        return
    # with a Main Attribute on the template, only that attribute's values are weight ranges
    main_condition = "AND (pt.main_attribute_id IS NULL OR pav.attribute_id = pt.main_attribute_id)" \
        if _column(cr, 'product_template', 'main_attribute_id') else ""
    cr.execute("""
        SELECT pt.livestock_variant, pt.purchase_product, pp.id, pav.from_kg, pav.to_kg
          FROM product_template pt
          JOIN product_product pp ON pp.product_tmpl_id = pt.id AND pp.active
          JOIN product_variant_combination pvc ON pvc.product_product_id = pp.id
          JOIN product_template_attribute_value ptav ON ptav.id = pvc.product_template_attribute_value_id
          JOIN product_attribute_value pav ON pav.id = ptav.product_attribute_value_id
         WHERE pt.purchase_product IS NOT NULL AND pt.livestock_variant IS NOT NULL
           AND pav.to_kg > pav.from_kg
           {main_condition}
         ORDER BY pt.livestock_variant, pt.purchase_product, pav.from_kg
    """.format(main_condition=main_condition))
    rows = cr.fetchall()
    env = api.Environment(cr, SUPERUSER_ID, {})
    Band = env['livestock.variant.line']
    created = skipped = 0
    for variant_id, purchase_id, product_id, from_kg, to_kg in rows:
        if Band.search_count([('variant_id', '=', variant_id), ('purchase_product_id', '=', purchase_id),
                              ('from_kg', '<', to_kg), ('to_kg', '>', from_kg)]):
            skipped += 1
            _logger.warning("Livestock band %s-%s kg of product %s overlaps an existing band: not created.",
                            from_kg, to_kg, product_id)
            continue
        purchase = env['product.product'].browse(purchase_id)
        if not purchase.check_stock:
            purchase.check_stock = True
        Band.create({'variant_id': variant_id, 'purchase_product_id': purchase_id,
                     'from_kg': from_kg, 'to_kg': to_kg, 'product_id': product_id})
        created += 1
    _logger.info("Livestock weight bands migrated: %s created, %s skipped (overlapping).", created, skipped)
