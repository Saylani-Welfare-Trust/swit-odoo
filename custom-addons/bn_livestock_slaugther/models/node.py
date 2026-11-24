from odoo import api, models


class LivestockSlaughterNode(models.Model):
    _inherit = 'livestock.slaugther'

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['source_location_id', 'transfer_location']


class LivestockRequisitionNode(models.Model):
    _name = 'livestock.requisition'
    _inherit = ['livestock.requisition', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['destination_location_id', 'source_location_id']


class LivestockMeatManagementNode(models.Model):
    _name = 'livestock.meat.management'
    _inherit = ['livestock.meat.management', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['location_id']


class DistributionCenterNode(models.Model):
    _name = 'distribution.center'
    _inherit = ['distribution.center', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['picking_id']


class LivestockCuttingNode(models.Model):
    _name = 'livestock.cutting'
    _inherit = ['livestock.cutting', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['warehouse_id', 'picking_id']


class LivestockCuttingMaterialNode(models.Model):
    _name = 'livestock.cutting.material'
    _inherit = ['livestock.cutting.material', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['warehouse_id', 'livestock_slaughter_id']
