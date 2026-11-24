from odoo import api, models


class ImportDonationNode(models.Model):
    _name = 'import.donation'
    _inherit = ['import.donation', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['warehouse_id', 'destination_location_id']
