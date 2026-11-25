import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Weight bands belong to the livestock product only (no Livestock Variant any
    more): a weight must fall in one band of the product. Bands of different
    variants of the same product that overlap are reduced to the first one
    (lowest weight, then oldest); the others are logged and removed."""
    cr.execute("SELECT to_regclass('livestock_variant_line')")
    if not cr.fetchone()[0]:
        return
    cr.execute("""SELECT id, purchase_product_id, from_kg, to_kg, product_id
                    FROM livestock_variant_line ORDER BY purchase_product_id, from_kg, id""")
    kept, removed = {}, []
    for band_id, product_id, from_kg, to_kg, received_id in cr.fetchall():
        bands = kept.setdefault(product_id, [])
        if any(from_kg < other_to and to_kg > other_from for other_from, other_to in bands):
            removed.append((band_id, product_id, from_kg, to_kg, received_id))
        else:
            bands.append((from_kg, to_kg))
    if removed:
        _logger.warning("Livestock weight bands overlapping another band of the same product, removed "
                        "(id, product, from kg, to kg, received as): %s", removed)
        cr.execute("DELETE FROM livestock_variant_line WHERE id IN %s", (tuple(r[0] for r in removed),))
    # the Livestock Variant records (Sadqa, Aqiqa, Qurbani ...) go with their model
    cr.execute("DELETE FROM ir_model_data WHERE model = 'livestock.variant'")
