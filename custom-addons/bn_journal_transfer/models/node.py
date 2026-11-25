from odoo import api, models


class JournalTransferNode(models.Model):
    _inherit = 'journal.transfer'

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['analytic_account_id']
