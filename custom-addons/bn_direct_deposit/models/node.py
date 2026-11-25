from odoo import api, models


class DirectDepositNode(models.Model):
    _inherit = 'direct.deposit'

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['analytic_account_id']
