import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Advance Donation products are loaded in the POS of the Advance Donation
    POS Action group only. Every POS user could take them so far: they keep it."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    group = env.ref('bn_advance_donation.advance_donation_pos_action_group')
    cashiers = env.ref('point_of_sale.group_pos_user').users.filtered(lambda u: not u.share)
    group.write({'users': [(4, user.id) for user in cashiers]})
    _logger.info("Advance Donation / POS Action given to %s POS users", len(cashiers))
