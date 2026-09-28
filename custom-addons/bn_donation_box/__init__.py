from . import models

from odoo import api, SUPERUSER_ID


def post_init_hook(env):
    """Fresh installs: bind the default Donation Box operation type to its warehouse."""
    env['stock.warehouse']._bn_migrate_legacy_donation_box_type()

    env = api.Environment(cr, SUPERUSER_ID, {})

    warehouse = env.ref('stock.warehouse0')
    donation_location = env['stock.location'].create({
        'name': 'Donation Box',
        'usage': 'customer',
        'location_id': warehouse.view_location_id.id,
    })

    env['stock.picking.type'].create({
        'name': 'Donation Box',
        'code': 'internal',
        'sequence_code': 'DBox',
        'use_create_lots': False,
        'use_existing_lots': True,
        'default_location_src_id': env.ref('stock.stock_location_stock').id,
        'default_location_dest_id': donation_location.id,
    })
