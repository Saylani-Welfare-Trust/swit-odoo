# After every module of the upgrade: the five dashboard access screens and the
# users' dashboard location lists are gone from the code (the dashboards follow
# the user's Branches / Sites). bn_stock_location's post-migrate read the lists
# into the users' Branches / Sites first; their tables are dropped.
ACCESS_CONFIG_TABLES = (
    'treasury_access_config', 'pos_order_access_config', 'donation_box_access_config',
    'pos_dd_report_access_config', 'livestock_access_config',
)
RELATION_TABLES = (
    # users' lists
    'treasury_user_analytic_rel', 'pos_user_analytic_rel', 'donation_box_user_analytic_rel',
    'pos_dd_report_user_analytic_rel', 'res_users_livestock_analytic_rel',
    # the screens' own lists
    'treasury_access_province_rel', 'treasury_access_city_rel', 'treasury_access_zone_rel',
    'pos_access_province_rel', 'pos_access_city_rel', 'pos_access_zone_rel', 'pos_access_shop_rel',
    'donation_box_access_province_rel', 'donation_box_access_city_rel', 'donation_box_access_zone_rel',
    'pos_dd_report_province_rel', 'pos_dd_report_city_rel', 'pos_dd_report_zone_rel', 'pos_dd_report_category_rel',
    'livestock_access_province_rel', 'livestock_access_city_rel', 'livestock_access_zone_rel',
)


def migrate(cr, version):
    for table in RELATION_TABLES + ACCESS_CONFIG_TABLES:
        cr.execute('DROP TABLE IF EXISTS "%s" CASCADE' % table)
