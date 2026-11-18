from odoo import models, fields, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'


    microfinance_line_ids = fields.One2many('microfinance', 'donee_id', string='Microfinance Lines')

    def _profile_after_register(self, microfinance):
        # Registering one Microfinance donee offers its application right away.
        if len(self) == 1 and microfinance:
            return self.action_print_microfinance_application()
        return super()._profile_after_register(microfinance)

    def action_print_microfinance_application(self):
        self.ensure_one()
        if 'Microfinance' not in self.category_id.mapped('name'):
            raise ValidationError('This action is only restricted for Microfinance Application.')

        # Open wizard to select microfinance scheme
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select Microfinance Scheme'),
            'res_model': 'microfinance.application.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_microfinance.microfinance_application_wizard_form').id,
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
            }
        }
