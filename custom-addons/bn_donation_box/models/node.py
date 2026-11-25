from odoo import api, models


class DonationBoxRequestNode(models.Model):
    _name = 'donation.box.request'
    _inherit = ['donation.box.request', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['warehouse_id', 'source_location_id', 'destination_location_id']


class DonationBoxComplainCenterNode(models.Model):
    _name = 'donation.box.complain.center'
    _inherit = ['donation.box.complain.center', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['zone_id', 'city_id']


class DonationBoxInstallationNode(models.Model):
    _name = 'donation.box.registration.installation'
    _inherit = ['donation.box.registration.installation', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['zone_id', 'city_id']
