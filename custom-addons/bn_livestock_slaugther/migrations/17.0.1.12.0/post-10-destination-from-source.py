from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """The Destination Location starts as the Source Location (users see the lines
    whose Destination Location is in their locations): lines not transferred yet
    get it, and a source first when they have none."""
    if not version:
        return
    cr.execute("""
        UPDATE livestock_slaugther SET transfer_location = source_location_id
         WHERE transfer_location IS NULL AND source_location_id IS NOT NULL
    """)
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['livestock.slaugther'].with_context(active_test=False).search(
        [('transfer_location', '=', False)])._init_destination()
