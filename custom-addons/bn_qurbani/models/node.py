from odoo import api, models


class CityScheduleNode(models.Model):
    _name = 'city.schedule'
    _inherit = ['city.schedule', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['location_id', 'slaughter_location_id']


class DistributionScheduleNode(models.Model):
    _name = 'distribution.schedule'
    _inherit = ['distribution.schedule', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['location_id', 'slaughter_location_id']


class SlaughterScheduleNode(models.Model):
    _name = 'slaughter.schedule'
    _inherit = ['slaughter.schedule', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['location_id', 'city_location_id']


class QurbaniCityDemandNode(models.Model):
    _name = 'qurbani.city.demand'
    _inherit = ['qurbani.city.demand', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['city_location_id']


class QurbaniSlaughterDemandNode(models.Model):
    _name = 'qurbani.slaughter.demand'
    _inherit = ['qurbani.slaughter.demand', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['slaughter_location_id', 'city_location_id']


class QurbaniSlotDemandNode(models.Model):
    _name = 'qurbani.slaughter.slot.demand'
    _inherit = ['qurbani.slaughter.slot.demand', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['slaughter_location_id']


class QurbaniCowSlaughterNode(models.Model):
    _name = 'qurbani.cow.slaughter'
    _inherit = ['qurbani.cow.slaughter', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['slaughter_location_id']


class QurbaniGoatSlaughterNode(models.Model):
    _name = 'qurbani.goat.slaughter'
    _inherit = ['qurbani.goat.slaughter', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['slaughter_location_id']


class QurbaniCowDistributionNode(models.Model):
    _name = 'qurbani.cow.distribution'
    _inherit = ['qurbani.cow.distribution', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['distribution_location_id', 'slaughter_location_id']


class QurbaniGoatDistributionNode(models.Model):
    _name = 'qurbani.goat.distribution'
    _inherit = ['qurbani.goat.distribution', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['distribution_location_id', 'slaughter_location_id']
