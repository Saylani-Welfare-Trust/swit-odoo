import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """The Donation Box button of the POS has its own group again (POS Action).
    It was shown to the Donation Box Managers: they keep it."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    group = env.ref('bn_donation_box.donation_box_pos_action_group')
    managers = env.ref('bn_donation_box.donation_box_manager_group').users
    group.write({'users': [(4, user.id) for user in managers]})
    _logger.info("Donation Box / POS Action given to %s Donation Box managers", len(managers))
