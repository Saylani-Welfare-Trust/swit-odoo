from odoo import api, models


class MaterialRequestNode(models.Model):
    _name = 'material.request'
    _inherit = ['material.request', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['source_location_id', 'dest_location_id']
