import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Who created a program document no longer gives access to it: every
    document without a Branch / Site gets one again from its sources, else from
    its creator (their employee's branch, now also their only Allowed Branch /
    Site). Runs after all modules are updated, so every program model is loaded.
    The ones still without are logged: only national users see them."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Mixin = env['node.document.mixin']
    for name in Mixin._node_document_models():
        Model = env[name].with_context(active_test=False, tracking_disable=True)
        records = Model.search([('node_id', '=', False)])
        if not records:
            continue
        env.add_to_compute(Model._fields['node_id'], records)
        records.flush_recordset(['node_id'])
        left = Model.search_count([('node_id', '=', False)])
        _logger.info("%s: %s documents without a Branch / Site, %s left (national users only)",
                     name, len(records), left)
