from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    medical_pos_role = fields.Selection(
        [('prescription', 'Prescription Desk'), ('billing', 'Billing Counter')],
        string="Medical Counter",
        help="Prescription Desk: add the prescribed products for a patient and approve them, no payment is taken.\n"
             "Billing Counter: select the patient, the approved products are loaded on the order to be paid.",
    )

    @api.onchange('is_medical_pos')
    def _onchange_is_medical_pos_role(self):
        if not self.is_medical_pos:
            self.medical_pos_role = False

    @api.constrains('is_medical_pos', 'medical_pos_role')
    def _check_medical_pos_role(self):
        for config in self:
            if config.medical_pos_role and not config.is_medical_pos:
                raise ValidationError(_("%s must be a Medical & Health POS to be a prescription desk or a billing counter.", config.name))
