from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

from .sadqa_jariya import DONEE_TAGS


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # A donee keeps one institutional portal login for all their applications
    sadqa_portal_login = fields.Char('Sadqa e Jariya Portal Login', readonly=True, copy=False)
    is_sadqa_jariya_donee = fields.Boolean('Sadqa e Jariya Donee', compute='_compute_is_sadqa_jariya_donee')
    # Institution donees only; the picture (image_1920) comes from the portal, of the contact person
    sadqa_contact_person = fields.Char('Contact Person / Manager', tracking=True)
    sadqa_area_id = fields.Many2one('sadqa.jariya.area', string='Area (Sadqa e Jariya)', tracking=True)

    @api.depends('category_id')
    def _compute_is_sadqa_jariya_donee(self):
        groups = self.env['sadqa.jariya']._donee_tag_groups()
        for partner in self:
            partner.is_sadqa_jariya_donee = len(groups) == len(DONEE_TAGS) and all(partner.category_id & tags for tags in groups)

    @api.model
    def action_sadqa_jariya_donees(self):
        """Sadqa e Jariya → Profile → Donee: the tags are matched when the menu opens"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Donee'),
            'res_model': 'res.partner',
            'views': [(self.env.ref(f'bn_profile_management.profile_management_view_{view}').id, view)
                      for view in ('kanban', 'tree', 'form')],
            'domain': self.env['sadqa.jariya']._donee_tag_domain(registered=False),
            'context': {'create': 0, 'delete': 0},
            'help': _('<p class="o_view_nocontent_smiling_face">Waiting for Sadqa e Jariya Donee\'s....</p>'),
        }

    def _sadqa_profile_popup(self):
        """The profile popup of Sadqa e Jariya's Record Search (its Save keeps it open)"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_sadqa_e_jariya.sadqa_jariya_profile_popup_form').id,
            'res_id': self.id,
            'target': 'new',
            'context': {'from_record_search': True, 'sadqa_jariya_profile': True},
        }

    def action_sadqa_profile_save(self):
        # the form saves the record before running the button, reopening keeps the popup
        return self._sadqa_profile_popup()

    # required on a Sadqa e Jariya donee before Register
    # (the contact number is the profile's Mobile)
    _sadqa_required_fields = ('sadqa_contact_person', 'mobile', 'sadqa_area_id', 'nearest_land_mark', 'date_of_birth')

    def action_register(self):
        for partner in self.filtered('is_sadqa_jariya_donee'):
            missing = [partner._fields[name].string for name in self._sadqa_required_fields if not partner[name]]
            if missing:
                raise ValidationError(_("Please fill in before registering the Sadqa-e-Jaria donee: %s") % ', '.join(missing))
            if partner.age < 18:
                raise ValidationError(_("Cannot Register the Institution for Sadqa-e-Jaria as the Manager age is below 18 years"))
        res = super().action_register()
        # a button returning nothing closes the popup
        if not res and self.env.context.get('sadqa_jariya_profile') and len(self) == 1:
            return self._sadqa_profile_popup()
        return res

    def action_change_request(self):
        res = super().action_change_request()
        if self.env.context.get('sadqa_jariya_profile'):
            return self._sadqa_profile_popup()
        return res

    def action_send_sadqa_portal_credentials(self):
        """Draft application for the donee; a new portal password too when they already have a login"""
        self.ensure_one()
        Application = self.env['sadqa.jariya']
        application = Application.search([('donee_id', '=', self.id), ('state', '=', 'draft')], order='id desc', limit=1)
        if not application:
            application = Application.create({'donee_id': self.id})
            message = _("Draft application %s created.") % application.name
        else:
            message = _("Draft application %s is open.") % application.name
        if self.sadqa_portal_login:
            # the portal keeps one login per donee, made with their first application
            application.action_reset_portal_password()
            message += ' ' + _("New portal password sent to %s.") % self.mobile
        else:
            message += ' ' + _("The portal login is sent with Send Form on the application.")
        in_popup = self.env.context.get('sadqa_jariya_profile')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Email / Whatsapp Credentials'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': self._sadqa_profile_popup() if in_popup else {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }
