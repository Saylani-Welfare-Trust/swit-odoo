# Warehouse form tabs of the previous version, replaced by the location roles
# (Is Meat / Goat / Chicken / Cutting / Kitchen Location). Their fields no longer
# exist: the views are removed before any module extending the warehouse form
# loads (every one of them depends on this module), or its view check fails.
OBSOLETE_VIEWS = (
    ('bn_livestock_slaugther', 'stock_view_warehouse_inherit_bn_livestock'),
    ('bn_kitchen', 'stock_view_warehouse_inherit_bn_kitchen'),
)


def migrate(cr, version):
    for module, name in OBSOLETE_VIEWS:
        cr.execute("SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s AND model = 'ir.ui.view'",
                   (module, name))
        row = cr.fetchone()
        if not row:
            continue
        cr.execute("DELETE FROM ir_ui_view WHERE id = %s", (row[0],))
        cr.execute("DELETE FROM ir_model_data WHERE module = %s AND name = %s", (module, name))
