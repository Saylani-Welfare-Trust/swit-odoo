from odoo import api, models


class MonthlyPlanningNode(models.Model):
    _name = 'monthly.planning'
    _inherit = ['monthly.planning', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['location_dest_id', 'source_location_id']
