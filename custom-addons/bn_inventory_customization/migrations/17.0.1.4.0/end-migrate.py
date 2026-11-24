def migrate(cr, version):
    """The Livestock Variant model is gone: its table and messages."""
    cr.execute("DELETE FROM mail_message WHERE model = 'livestock.variant'")
    cr.execute("DELETE FROM mail_followers WHERE res_model = 'livestock.variant'")
    cr.execute('DROP TABLE IF EXISTS "livestock_variant" CASCADE')
