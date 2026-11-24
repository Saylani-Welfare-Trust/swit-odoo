from odoo import api, models


class AdvanceDonationNode(models.Model):
    _name = 'advance.donation'
    _inherit = ['advance.donation', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + []
