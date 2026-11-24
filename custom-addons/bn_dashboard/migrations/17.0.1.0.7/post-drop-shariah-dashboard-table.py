def migrate(cr, version):
    """The Shariah Law Dashboard holds no records (abstract model since 17.0.1.0.7):
    its empty transient table is dropped."""
    cr.execute('DROP TABLE IF EXISTS "shariah_dashboard" CASCADE')
