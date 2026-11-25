import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

MODELS = ('livestock.requisition', 'livestock.cutting', 'livestock.cutting.material',
          'livestock.meat.management', 'distribution.center')


def migrate(cr, version):
    """Who created a livestock document no longer gives access to it: the
    documents without a Branch / Site get one again (their creator's only
    Allowed Branch / Site now counts); the ones still without are logged, only
    national users see them."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for name in MODELS:
        Model = env[name].with_context(active_test=False)
        records = Model.search([('node_id', '=', False)])
        if records:
            env.add_to_compute(Model._fields['node_id'], records)
            records.flush_recordset(['node_id'])
            left = Model.search_count([('node_id', '=', False)])
            _logger.info("%s: %s documents without a Branch / Site, %s left (national users only)",
                         name, len(records), left)
