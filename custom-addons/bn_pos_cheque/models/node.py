from odoo import api, models


class PosChequeNode(models.Model):
    _inherit = 'pos.cheque'

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['analytic_account_id']
