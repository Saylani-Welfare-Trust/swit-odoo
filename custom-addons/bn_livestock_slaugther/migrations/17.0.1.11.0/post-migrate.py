from odoo import SUPERUSER_ID, api
from odoo.tools.sql import column_exists

# role flag: the warehouse column of the previous version, the names the steps used before
ROLES = {
    'is_meat_location': ('livestock_meat_location_id', ('Meat',)),
    'is_goat_location': ('livestock_goat_location_id', ('Goat',)),
    'is_chicken_location': ('livestock_chicken_location_id', ('Chicken',)),
    'is_cutting_location': ('livestock_cutting_location_id', ('Livestock Cutting',)),
}


def migrate(cr, version):
    """A warehouse may hold several Meat / Goat / Chicken / Cutting locations:
    they are marked on the location, and each document chooses its own.

    - The locations used until now (set on the warehouse, or found by name) are
      marked, so the flow goes on as before.
    - Open documents get their warehouse's only location of each role (several:
      chosen on the document before the step).
    - The warehouse columns of the previous version are dropped."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Location = env['stock.location'].with_context(active_test=False)
    for flag, (column, names) in ROLES.items():
        ids = set()
        if column_exists(cr, 'stock_warehouse', column):
            cr.execute('SELECT DISTINCT "%s" FROM stock_warehouse WHERE "%s" IS NOT NULL' % (column, column))
            ids |= {row[0] for row in cr.fetchall()}
        ids |= set(Location.search([('name', 'in', names), ('usage', 'in', ('internal', 'transit'))]).ids)
        Location.browse(list(ids)).exists().filtered(lambda l: not l[flag]).write({flag: True})
        if column_exists(cr, 'stock_warehouse', column):
            cr.execute('ALTER TABLE stock_warehouse DROP COLUMN "%s"' % column)

    env['livestock.slaugther'].search([('state', 'in', ('not_received', 'slaughtered'))])._fill_default_locations()
    env['livestock.cutting.material'].search([('state', '!=', 'done')])._fill_default_locations()
    Cutting = env['livestock.cutting']
    for cutting in Cutting.search([('is_picking', '=', False)]):
        warehouse = cutting.warehouse_id
        if not cutting.cutting_location_id and warehouse:
            cutting.cutting_location_id = Location._single_role_location('is_cutting_location', warehouse)
