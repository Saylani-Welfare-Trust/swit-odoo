from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Unrestricted Custom Access users see every warehouse today: they get All
    Branches / Sites, so switching them to Branch / Site Access keeps it."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['node.setup']._fill_national()
