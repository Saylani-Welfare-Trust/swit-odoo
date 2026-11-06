import base64
import logging
import re

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

from .sadqa_jariya import DONEE_TAGS

_logger = logging.getLogger(__name__)


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
            # _origin: on a donee not saved yet (Record Search popup) the tags are new-record copies of the real tags
            tags_set = partner.category_id._origin
            partner.is_sadqa_jariya_donee = len(groups) == len(DONEE_TAGS) and all(tags_set & tags for tags in groups)

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
    _sadqa_required_fields = ('sadqa_contact_person', 'mobile', 'cnic_no', 'street', 'city', 'sadqa_area_id', 'nearest_land_mark', 'date_of_birth')

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

    def action_print_info(self):
        res = super().action_print_info()
        if len(self) == 1 and self.is_sadqa_jariya_donee:
            return self.env.ref('bn_sadqa_e_jariya.action_report_sadqa_jariya_donee_profile').report_action(self)
        return res

    def _sadqa_profile_form_attachment(self):
        """The Sadqa e Jariya profile form as a PDF on the donee, with an access token for its link
        (earlier ones are kept: the donee's WhatsApp link and the chatter point to them)"""
        self.ensure_one()
        pdf, _type = self.env['ir.actions.report']._render_qweb_pdf('bn_sadqa_e_jariya.action_report_sadqa_jariya_donee_profile', self.ids)
        filename = 'Profile_%s.pdf' % re.sub(r'[^A-Za-z0-9]+', '_', self.primary_registration_id or self.name or str(self.id)).strip('_')
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf),
            'res_model': 'res.partner',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        attachment.generate_access_token()
        return attachment

    def _send_sadqa_profile_whatsapp(self, attachment):
        """The profile form as the document of the approved profile template (the donation receipt one has the wrong text)"""
        company = self.env.company
        if not company.institution_profile_whatsapp_template:
            raise UserError(_("set the Profile Form WhatsApp Template in the Company settings"))
        number = self.whatsapp or self.mobile
        if not number:
            raise UserError(_("no WhatsApp number"))
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        self.env['whatsapp.service'].send_document_template(
            number,
            company.institution_profile_whatsapp_template,
            company.institution_profile_whatsapp_namespace,
            f"{base_url}/web/content/{attachment.id}?access_token={attachment.access_token}&download=true",
            attachment.name,
            language=company.institution_profile_whatsapp_language,
        )

    def _send_sadqa_profile_email(self, attachment):
        if not self.email:
            raise UserError(_("no email address"))
        template = self.env.ref('bn_sadqa_e_jariya.mail_template_sadqa_jariya_profile_form')
        mail_id = template.send_mail(self.id, force_send=True, email_values={'attachment_ids': [(4, attachment.id)]})
        # a sent mail is deleted (auto_delete), a failed one stays with the reason
        mail = self.env['mail.mail'].sudo().browse(mail_id).exists()
        if mail.state == 'exception':
            raise UserError(mail.failure_reason or _("the mail server refused it"))

    def action_send_sadqa_profile_form(self):
        """Draft application for the donee, and their profile form by WhatsApp and email
        (the portal login only goes with Send Form / Reset Portal Password on the application)"""
        self.ensure_one()
        Application = self.env['sadqa.jariya']
        application = Application.search([('donee_id', '=', self.id), ('state', '=', 'draft')], order='id desc', limit=1)
        if not application:
            application = Application.create({'donee_id': self.id})
            message = _("Draft application %s created.") % application.name
        else:
            message = _("Draft application %s is open.") % application.name

        attachment = self._sadqa_profile_form_attachment()
        sent, failed = [], []
        for channel, send in ((_('WhatsApp'), self._send_sadqa_profile_whatsapp), (_('Email'), self._send_sadqa_profile_email)):
            try:
                send(attachment)
                sent.append(channel)
            except Exception as e:
                _logger.warning("Sadqa e Jariya donee %s: profile form %s failed: %s", self.id, channel, e)
                failed.append('%s (%s)' % (channel, str(e) or e.__class__.__name__))

        if sent:
            message += ' ' + _("Profile form sent by %s.") % _(' and ').join(sent)
            self.message_post(body=_("📨 Donee profile form sent by %s.") % _(' and ').join(sent), attachment_ids=attachment.ids)
        if failed:
            message += ' ' + _("Not sent: %s.") % ', '.join(failed)
        in_popup = self.env.context.get('sadqa_jariya_profile')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Send Profile Form'),
                'message': message,
                'type': 'warning' if failed else 'success',
                'sticky': bool(failed),
                'next': self._sadqa_profile_popup() if in_popup else {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }
