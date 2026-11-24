from odoo import api, models


class DonationInKindNode(models.Model):
    _inherit = 'donation.in.kind'

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['location_id', 'analytical_account_id']
