from odoo import api, models


class BranchKitchenRequestNode(models.Model):
    _name = 'branch.kitchen.request'
    _inherit = ['branch.kitchen.request', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['branch_id']
