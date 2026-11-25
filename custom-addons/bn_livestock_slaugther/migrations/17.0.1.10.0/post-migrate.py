from odoo import SUPERUSER_ID, api
from odoo.tools.sql import column_exists

# the locations the slaughter steps used before (by name)
OLD_SLAUGHTER_NAMES = ('Slaughter Stock', 'Livestock Slaugther')


def migrate(cr, version):
    """Slaughter locations are the locations marked "Is Slaughter Location" (a
    warehouse may hold several), one chosen per animal. The locations the
    slaughter steps used until now (by name, or the warehouse's Slaughter Stock
    of the previous version) are marked, so the flow goes on as before. Open
    animals get their location in 17.0.1.11.0."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Location = env['stock.location'].with_context(active_test=False)
    old = Location.search([('name', 'in', OLD_SLAUGHTER_NAMES), ('usage', 'in', ('internal', 'transit'))])
    if column_exists(cr, 'stock_warehouse', 'livestock_slaughter_location_id'):
        cr.execute('SELECT DISTINCT livestock_slaughter_location_id FROM stock_warehouse '
                   'WHERE livestock_slaughter_location_id IS NOT NULL')
        old |= Location.browse([row[0] for row in cr.fetchall()]).exists()
        cr.execute('ALTER TABLE stock_warehouse DROP COLUMN livestock_slaughter_location_id')
    old.filtered(lambda l: not l.is_slaughter_location).write({'is_slaughter_location': True})
