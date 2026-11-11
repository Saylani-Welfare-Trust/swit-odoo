from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    is_medical_pos = fields.Boolean(
        string="Medical & Health POS",
        help="Patients (registered donees tagged Medical) are the customers of this POS instead of donors, "
             "and new patients can be registered from its customer screen.",
    )
