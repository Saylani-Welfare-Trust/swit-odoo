# After every module of the upgrade: the previous versions' Allowed Locations /
# Warehouses of the users are gone from the code; their tables were read by
# post-migrate (Branches / Sites filled) and are dropped.
OLD_TABLES = ('res_users_stock_location_rel', 'res_users_stock_warehouse_rel')


def migrate(cr, version):
    for table in OLD_TABLES:
        cr.execute('DROP TABLE IF EXISTS "%s" CASCADE' % table)
