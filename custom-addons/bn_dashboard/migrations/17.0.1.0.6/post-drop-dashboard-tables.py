DASHBOARD_TABLES = (
    'profit_loss_dashboard', 'livestock_dashboard',
    'donation_box_dashboard', 'donation_inflow_dashboard', 'profile_management_dashboard',
)


def migrate(cr, version):
    """The dashboards hold no records (abstract models since 17.0.1.0.4 / 17.0.1.0.6):
    their old, empty transient tables are dropped."""
    for table in DASHBOARD_TABLES:
        cr.execute('DROP TABLE IF EXISTS "%s" CASCADE' % table)
