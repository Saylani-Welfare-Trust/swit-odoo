from odoo import api, models


class RiderShiftNode(models.Model):
    _name = 'rider.shift'
    _inherit = ['rider.shift', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['rider_id']


class RiderScheduleDayNode(models.Model):
    _name = 'rider.schedule.day'
    _inherit = ['rider.schedule.day', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['zone_id', 'city_id']
