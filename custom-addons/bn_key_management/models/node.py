from odoo import api, models


class KeyBunchNode(models.Model):
    _name = 'key.bunch'
    _inherit = ['key.bunch', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['zone_id', 'city_id']


class KeyIssuanceNode(models.Model):
    _name = 'key.issuance'
    _inherit = ['key.issuance', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['zone_id', 'city_id']


class KeyNode(models.Model):
    _name = 'key'
    _inherit = ['key', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['key_bunch_id']
