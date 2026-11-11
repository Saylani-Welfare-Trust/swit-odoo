from odoo import _, fields, models


class PatientRegisterWizard(models.TransientModel):
    _name = 'mh.patient.register.wizard'
    _description = 'Register Patient'

    name = fields.Char('Name', required=True)
    mobile = fields.Char('Contact No.', required=True, help="10 digits, e.g. 3001234567")
    cnic_no = fields.Char('CNIC No.', required=True, help="XXXXX-XXXXXXX-X")
    date_of_birth = fields.Date('Date of Birth', required=True)

    def action_register(self):
        self.ensure_one()
        patient, existing = self.env['res.partner']._mh_register_patient({
            'name': self.name,
            'mobile': self.mobile,
            'cnic_no': self.cnic_no,
            'date_of_birth': self.date_of_birth,
        })
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Patient'),
            'res_model': 'mh.patient',
            'res_id': patient.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }
        if existing:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'sticky': False,
                    'message': _("%(name)s (%(reg)s) is already a registered donee with this CNIC: tagged as patient.",
                                 name=patient.name, reg=patient.primary_registration_id or ''),
                    'next': action,
                },
            }
        return action
