from . import models


def post_init_hook(env):
    """Fresh installs: every warehouse gets its Donation Box operation type."""
    env['stock.warehouse']._bn_setup_donation_box_types()
