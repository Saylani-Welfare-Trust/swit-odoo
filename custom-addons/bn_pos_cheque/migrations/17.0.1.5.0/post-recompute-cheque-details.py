import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Donor, amount, analytic account and reference of POS cheques were
    computed once, before their order existed, and stayed empty: compute
    them again from the order."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    cheques = env['pos.cheque'].with_context(active_test=False).search([])
    for name in ('donor_id', 'analytic_account_id', 'amount', 'order_reference'):
        env.add_to_compute(env['pos.cheque']._fields[name], cheques)
    env.flush_all()
    _logger.info('POS cheques: details computed again for %s cheques', len(cheques))
