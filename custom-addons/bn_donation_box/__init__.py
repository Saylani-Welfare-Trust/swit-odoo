from . import models


def post_init_hook(env):
    """Fresh installs: bind the default Donation Box operation type to its warehouse."""
    env['stock.warehouse']._bn_migrate_legacy_donation_box_type()
