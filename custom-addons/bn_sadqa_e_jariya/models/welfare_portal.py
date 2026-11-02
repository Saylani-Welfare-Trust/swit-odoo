import json
import logging
import secrets
import string

import requests

from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Institution flow: completed -> Send Form -> form_sent -> Check Portal Status -> form_filled
# -> Send for Inquiry -> send_for_inquiry -> Check Portal Status -> inquiry -> approvals as in bn_welfare
INSTITUTION_FLOW = ['completed', 'form_sent', 'form_filled', 'send_for_inquiry']


class Welfare(models.Model):
    _inherit = 'welfare'

    state = fields.Selection(selection_add=[
        ('form_sent', 'Form Sent'),
        ('form_filled', 'Form Filled'),
        ('send_for_inquiry',),
    ], ondelete={
        'form_sent': lambda recs: recs.write({'state': 'completed'}),
        'form_filled': lambda recs: recs.write({'state': 'completed'}),
    })

    def _make_institution_api_call(self, endpoint, data):
        """POST to the institution portal, returns the response's 'data'"""
        company = self.env.company
        if not company.welfare_instituiton_url or not endpoint:
            raise UserError(_("Institution portal URL / endpoint is not set in the Company settings."))
        url = self.clean_url(f"{company.welfare_instituiton_url}{endpoint}")
        headers = {
            'x-odoo-auth-key': f'{company.odoo_auth_institution_key}',
            'Content-Type': 'application/json'
        }
        data = json.loads(json.dumps(data, default=str))
        # payload is not logged, it may hold the donee's password
        _logger.info("Institution portal call to %s for welfare %s", url, self.ids)
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise UserError(_("Institution portal request failed: %s") % e)
        return response.json().get('data')

    def _generate_portal_password(self):
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(10))

    def action_send_institution_form(self):
        """Create the donee's institution portal login and send it on WhatsApp"""
        company = self.env.company
        if not company.institution_login_whatsapp_template or not company.institution_login_whatsapp_namespace:
            raise UserError(_("Set the Portal Login WhatsApp Template and Namespace in the Company settings first."))

        for rec in self:
            if rec.is_individual or rec.state != 'completed':
                raise UserError(_("[%s] Only completed institution disbursements can be sent the form.") % rec.display_name)
            donee = rec.donee_id
            if not donee.email:
                raise UserError(_("[%s] Donee %s has no email, the portal login needs one.") % (rec.display_name, donee.name))
            if not donee.mobile:
                raise UserError(_("[%s] Donee %s has no WhatsApp / mobile number.") % (rec.display_name, donee.name))

            password = rec._generate_portal_password()
            # Creates the account, or resets its password when the form is sent again
            rec._make_institution_api_call(company.create_institution_account_endpoint, {
                "odooId": rec.id,
                "doneeOdooId": donee.id,
                "name": donee.name,
                "email": donee.email,
                "password": password,
                "cnic": donee.cnic_no.replace("-", "") if donee.cnic_no else "",
                "whatsapp": donee.mobile,
            })
            try:
                self.env['whatsapp.service'].send_text_template(
                    donee.mobile,
                    company.institution_login_whatsapp_template,
                    company.institution_login_whatsapp_namespace,
                    [donee.name, company.institution_portal_login_url, donee.email, password],
                    language=company.institution_login_whatsapp_language,
                )
            except Exception as e:
                raise UserError(_("[%s] Portal login created but WhatsApp failed, send the form again: %s") % (rec.display_name, e))

            rec.state = 'form_sent'
            rec.message_post(body=_("📨 Portal login (%s) sent on WhatsApp to %s.") % (donee.email, donee.mobile))

        return self._show_notification(_('Send Form'), _('Portal login sent to the donee on WhatsApp.'), 'success')

    def _get_institution_portal_application(self):
        """Application the donee filled on the institution portal for this record, None if not yet"""
        self.ensure_one()
        return self._make_institution_api_call(
            self.env.company.institution_application_status_endpoint, {"odooId": self.id}
        ) or None

    def _check_institution_portal_status(self):
        self.ensure_one()
        Fetch = self.env['welfare.institution.fetch.log']
        application = self._get_institution_portal_application()

        if self.state == 'form_sent':
            if not application or not application.get('form'):
                return self._show_notification(_('Check Portal Status'), _('The donee has not filled the form yet.'), 'warning')
            self.write(Fetch._prepare_application_vals(application))
            Fetch._create_application_details(self, application)
            Fetch._mark_application_synced(self)
            self.state = 'form_filled'
            self.message_post(body=_("📝 Form filled by the donee on the portal (%s).") % (application.get('token') or ''))
            return self._show_notification(_('Check Portal Status'), _('Form filled, you can now Send for Inquiry.'), 'success')

        # send_for_inquiry: wait for a completed inquiry report
        reports = (application or {}).get('inquiryReports') or []
        if not any(report.get('status') == 'completed' for report in reports):
            return self._show_notification(_('Check Portal Status'), _('The inquiry officer has not completed the inquiry yet.'), 'warning')
        Fetch._create_inquiry_reports(self, reports)
        self.state = 'inquiry'
        self.message_post(body=_("🔎 Inquiry completed on the portal."))
        return self._show_notification(_('Check Portal Status'), _('Inquiry completed, moved to Inquiry Officer.'), 'success')

    def action_check_portal_status(self):
        self.ensure_one()
        if not self.is_individual:
            return self._check_institution_portal_status()
        return super().action_check_portal_status()

    def action_send_for_inquiry(self):
        institutions = self.filtered(lambda r: not r.is_individual)
        if not institutions:
            return super().action_send_for_inquiry()
        if institutions != self:
            raise UserError(_("Send individual and institution disbursements for inquiry separately."))

        for rec in institutions:
            if rec.state != 'form_filled':
                raise UserError(_("[%s] The donee has to fill the form before it can be sent for inquiry.") % rec.display_name)
            officer = rec.employee_id
            if not officer:
                raise UserError(_("[%s] Select the Inquiry Officer first.") % rec.display_name)
            rec._make_institution_api_call(self.env.company.assign_institution_inquiry_endpoint, {
                "odooId": rec.id,
                "applicationId": rec.old_system_id,
                "inquiryOfficer": {
                    "employeeId": officer.barcode,
                    "name": officer.name,
                    "email": officer.work_email,
                },
            })
            rec.state = 'send_for_inquiry'
            rec.message_post(body=_("📤 Sent for inquiry to %s on the portal.") % officer.name)

        return self._show_notification(_('Send for Inquiry'), _('Inquiry officer assigned on the portal.'), 'success')

    def action_reverse_state(self):
        institutions = self.filtered(lambda r: not r.is_individual and r.state in INSTITUTION_FLOW[1:])
        for rec in institutions:
            rec.state = INSTITUTION_FLOW[INSTITUTION_FLOW.index(rec.state) - 1]
        return super(Welfare, self - institutions).action_reverse_state()
