from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Branch / Site set-up from the location-based one: warehouses' Branch / Site,
    users' Allowed Branches / Sites, national access. Access itself is unchanged:
    the record rules still use the locations; review Inventory > Configuration >
    Branch / Site Set-up Check before the switch."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['node.setup']._fill()
