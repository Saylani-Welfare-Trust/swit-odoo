from odoo import api, models


class MicrofinanceNode(models.Model):
    _name = 'microfinance'
    _inherit = ['microfinance', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['warehouse_location_id', 'recovered_location_id']
