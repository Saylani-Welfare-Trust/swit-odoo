from odoo import SUPERUSER_ID, api
from odoo.tools.sql import column_exists


def migrate(cr, version):
    """Kitchen Production used the first location named like "kitchen" and the
    first named like "stock" in the country. Kitchens are now the locations
    marked "Is Kitchen Location" (a warehouse may hold several); each request
    names its kitchen and the ingredients come from that kitchen's warehouse.

    - Today's kitchen locations (named Kitchen, or set on a warehouse by the
      previous version) are marked.
    - Open requests get their kitchen: the one of the warehouse chosen on them
      by the previous version, else the only kitchen."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Location = env['stock.location'].with_context(active_test=False)
    kitchens = Location.search([('name', '=ilike', 'kitchen'), ('usage', '=', 'internal')])
    by_warehouse = {}
    if column_exists(cr, 'stock_warehouse', 'kitchen_location_id'):
        cr.execute('SELECT id, kitchen_location_id FROM stock_warehouse WHERE kitchen_location_id IS NOT NULL')
        by_warehouse = dict(cr.fetchall())
        kitchens |= Location.browse(list(by_warehouse.values())).exists()
    kitchens.filtered(lambda l: not l.is_kitchen_location).write({'is_kitchen_location': True})

    Request = env['branch.kitchen.request']
    open_requests = Request.search([('state', '!=', 'done'), ('kitchen_location_id', '=', False)])
    if column_exists(cr, 'branch_kitchen_request', 'kitchen_warehouse_id'):
        cr.execute('SELECT id, kitchen_warehouse_id FROM branch_kitchen_request WHERE kitchen_warehouse_id IS NOT NULL')
        for request_id, warehouse_id in cr.fetchall():
            request = open_requests.filtered(lambda r: r.id == request_id)
            if request and by_warehouse.get(warehouse_id):
                request.kitchen_location_id = by_warehouse[warehouse_id]
        cr.execute('ALTER TABLE branch_kitchen_request DROP COLUMN kitchen_warehouse_id')
    if column_exists(cr, 'stock_warehouse', 'kitchen_location_id'):
        cr.execute('ALTER TABLE stock_warehouse DROP COLUMN kitchen_location_id')
    only = Request._default_kitchen_location()
    if only:
        open_requests.filtered(lambda r: not r.kitchen_location_id).write({'kitchen_location_id': only.id})
