from odoo import api, models


class MedicalPrescriptionNode(models.Model):
    _inherit = 'medical.prescription'

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['desk_config_id']
