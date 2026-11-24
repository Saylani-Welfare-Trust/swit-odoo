from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Kitchen Production used the first location named like "kitchen" and the first
    named like "stock". Each warehouse now has its own Kitchen Location and each
    request its Kitchen Warehouse: the existing kitchen location(s) are kept on
    their warehouse, and open requests get the kitchen warehouse when there is one."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Location = env['stock.location']
    for warehouse in env['stock.warehouse'].search([('kitchen_location_id', '=', False)]):
        kitchen = Location.search([('usage', '=', 'internal'), ('name', 'ilike', 'kitchen'),
                                   ('id', 'child_of', warehouse.view_location_id.id)], order='id', limit=1)
        if kitchen:
            warehouse.kitchen_location_id = kitchen
    kitchens = env['stock.warehouse'].search([('kitchen_location_id', '!=', False)])
    if len(kitchens) == 1:
        env['branch.kitchen.request'].search([('state', '!=', 'done'), ('kitchen_warehouse_id', '=', False)]).write(
            {'kitchen_warehouse_id': kitchens.id})
