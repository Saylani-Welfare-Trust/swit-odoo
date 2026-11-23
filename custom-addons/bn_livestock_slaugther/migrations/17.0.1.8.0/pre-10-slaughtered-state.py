def migrate(cr, version):
    """The Received state of livestock slaughter is now Slaughtered."""
    if not version:
        return  # fresh install, nothing to migrate
    cr.execute("UPDATE livestock_slaugther SET state = 'slaughtered' WHERE state = 'received'")
