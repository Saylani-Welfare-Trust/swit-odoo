from odoo import SUPERUSER_ID, api

# the locations the slaughter steps used before (by name)
OLD_SLAUGHTER_NAMES = ('Slaughter Stock', 'Livestock Slaugther')


def migrate(cr, version):
    """Slaughter locations are the locations marked "Is Slaughter Location", one
    chosen per animal:
    - the locations the slaughter steps used until now are marked, so the flow
      goes on as before;
    - Draft animals get their warehouse's slaughter location when it has only one
      (the others are chosen on the record before Slaughtered)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Location = env['stock.location'].with_context(active_test=False)
    old = Location.search([('name', 'in', OLD_SLAUGHTER_NAMES), ('usage', 'in', ('internal', 'transit')),
                           ('is_slaughter_location', '=', False)])
    old.write({'is_slaughter_location': True})
    for record in env['livestock.slaugther'].search([('state', '=', 'not_received'),
                                                     ('slaughter_location_id', '=', False)]):
        slaughter = record._default_slaughter_location()
        if slaughter:
            record.slaughter_location_id = slaughter
