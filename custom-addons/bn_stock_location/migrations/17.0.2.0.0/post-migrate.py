import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """One basis for everyone: what a user sees comes from their Branches / Sites.
    The location-based inputs (Allowed Locations / Warehouses, employee branch,
    dashboard access lists) are removed in this version: before their tables go,
    every user who has no Branch / Site yet gets them from those inputs, and the
    national groups get All Branches / Sites. Users that already have Branches /
    Sites are not changed."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    stats = env['node.setup']._fill()
    _logger.info("Branch / Site: users filled from the previous access before its removal: %s", stats)
