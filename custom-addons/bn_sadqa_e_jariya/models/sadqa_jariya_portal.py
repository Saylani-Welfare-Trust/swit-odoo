import json
import logging
import re
import secrets
import string

import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from .sadqa_jariya import FORM_KINDS

_logger = logging.getLogger(__name__)

# Sadqa Jaria institutional integration: POST <portal>/rpc/odoo/institutional/<operation>, {"json": ...} envelope
INSTITUTIONAL_RPC = '/rpc/odoo/institutional/'
EXPORT_PAGE_SIZE = 50


# Portal flow: completed -> Send Form (createApplication) -> form_sent -> Portal Sync imports the submitted form
# -> form_filled -> Send for Inquiry (assignOfficer) -> send_for_inquiry -> Portal Sync imports the inquiry -> inquiry
class SadqaJariya(models.Model):
    _inherit = 'sadqa.jariya'

    def _clean_url(self, url):
        # zero-width space, BOM and non-breaking space pasted with the settings
        return url.strip().replace('​', '').replace('﻿', '').replace(' ', '')

    @api.model
    def _portal_configured(self):
        company = self.env.company
        return bool(company.welfare_instituiton_url and company.odoo_auth_institution_key)

    @api.model
    def _portal_base_url(self):
        """Portal server address, also when the setting already ends with /rpc, /rpc/odoo or /rpc/odoo/institutional"""
        base = self._clean_url(self.env.company.welfare_instituiton_url).rstrip('/')
        for suffix in INSTITUTIONAL_RPC.rstrip('/'), '/rpc/odoo', '/rpc':
            if base.endswith(suffix):
                return base[:-len(suffix)]
        return base

    @api.model
    def _portal_call(self, operation, payload):
        """Call an institutional operation, returns its result (the response's 'json')"""
        company = self.env.company
        if not self._portal_configured():
            raise UserError(_("Set the Welfare Institution URL and Odoo Auth Institution Key in the Company settings."))
        url = self._portal_base_url() + INSTITUTIONAL_RPC + operation
        headers = {
            # pasted keys often bring a space / line break / invisible character with them
            'x-odoo-auth-key': self._clean_url(company.odoo_auth_institution_key or ''),
            'Content-Type': 'application/json'
        }
        body = {'json': json.loads(json.dumps(payload, default=str))}
        # payload is not logged, it may hold the donee's password
        _logger.info("Sadqa e Jariya portal call %s", operation)
        try:
            response = requests.post(url, headers=headers, json=body, timeout=30)
        except requests.exceptions.RequestException as e:
            raise UserError(_("Portal %s failed: %s") % (operation, e))
        try:
            result = response.json() or {}
        except ValueError:
            result = {}
        if not response.ok:
            # oRPC error: {"json": {"code": "CONFLICT", "status": 409, "message": "..."}};
            # anything else (an HTML 404 page...) is usually a wrong Welfare Institution URL
            error = result.get('json') if isinstance(result.get('json'), dict) else {}
            message = error.get('message') or ' '.join(re.sub(r'<[^>]+>', ' ', response.text or '').split())[:300]
            raise UserError(_("Portal %(operation)s: %(code)s %(message)s\nCalled: %(url)s",
                              operation=operation,
                              code=error.get('code') or response.status_code,
                              message=message,
                              url=url))
        return result.get('json')

    @api.model
    def _portal_export(self, operation):
        """All rows of a pending export (getSubmittedForms / getCompletedInquiries), page by page"""
        rows, cursor, seen = [], None, set()
        while True:
            payload = {'limit': EXPORT_PAGE_SIZE}
            if cursor:
                payload['cursor'] = cursor
            page = self._portal_call(operation, payload) or {}
            rows += page.get('data') or []
            cursor = page.get('nextCursor')
            if not cursor or cursor in seen:
                return rows
            seen.add(cursor)

    def _generate_portal_password(self):
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(10))

    def _portal_login_email(self, domain):
        """Login made from the donee name and form number, e.g. masjidnoor.ins-2026-0001@<domain>"""
        self.ensure_one()
        name = re.sub(r'[^a-z0-9]', '', (self.donee_id.name or '').lower())[:30] or 'donee'
        number = re.sub(r'[^a-z0-9]+', '-', (self.name or str(self.id)).lower()).strip('-')
        return f"{name}.{number}@{domain.lower()}"

    def _portal_donee(self):
        donee = self.donee_id
        mobile = re.sub(r'\D', '', donee.mobile or '')
        vals = {
            'odooId': donee.id,
            'name': donee.name,
            # 03001234567, the profile keeps 10 digits
            'whatsapp': '0' + mobile if len(mobile) == 10 else mobile,
            'cnic': re.sub(r'\D', '', donee.cnic_no or ''),
        }
        address = ', '.join(part for part in (donee.street, donee.street2, donee.city) if part)
        if address:
            vals['address'] = address
        area = donee.sadqa_area_id or donee.area
        if area:
            vals['area'] = area.name
        return vals

    def _portal_base_info(self):
        """Basic information known in Odoo, locked for the donee and the officer on the portal
        (the portal defaults cnicNumber / contactNumber / whatsappNumber from the donee itself)"""
        donee = self.donee_id
        values = {
            'requestDate': fields.Date.to_string(self.date) if self.date else False,
            # the donee is the institution
            'institutionName': self.institute_name or donee.name,
            'institutionAddress': self.address or ', '.join(part for part in (donee.street, donee.street2, donee.city) if part),
            # the portal would default it to the donee name, i.e. the institution's
            'responsiblePersonName': donee.sadqa_contact_person,
            'accountNumber': self.account_number,
            'fatherName': donee.father_name,
            'phoneNumber': donee.phone,
            'applicantLocationLink': self.applicant_location_link,
        }
        return {key: value for key, value in values.items() if value}

    def _portal_login_channel(self):
        """WhatsApp once an approved template is set in the Company settings, SMS until then"""
        company = self.env.company
        if company.institution_login_whatsapp_template and company.institution_login_whatsapp_namespace:
            return 'WhatsApp'
        return 'SMS'

    def _portal_login_sms(self, login, password_text):
        lines = [_("Assalam-o-Alaikum %s,") % self.donee_id.name, _("Your Sadqa e Jariya portal login:")]
        if self.env.company.institution_portal_login_url:
            lines.append(self.env.company.institution_portal_login_url)
        lines += [_("Email: %s") % login, _("Password: %s") % password_text]
        return '\n'.join(lines)

    def _send_portal_login(self, login, password_text):
        """Send the portal login to the donee, returns the error if it couldn't be sent"""
        self.ensure_one()
        company = self.env.company
        try:
            if self._portal_login_channel() == 'WhatsApp':
                self.env['whatsapp.service'].send_text_template(
                    self.donee_id.mobile,
                    company.institution_login_whatsapp_template,
                    company.institution_login_whatsapp_namespace,
                    [self.donee_id.name, company.institution_portal_login_url, login, password_text],
                    language=company.institution_login_whatsapp_language,
                )
            else:
                self.env['sms.service'].send_sms(self.donee_id.mobile, self._portal_login_sms(login, password_text))
        except Exception as e:
            _logger.warning("Sadqa e Jariya %s: portal login %s failed: %s", self.name, self._portal_login_channel(), e)
            return str(e) or e.__class__.__name__
        return None

    def action_send_institution_form(self):
        """createApplication: the donee gets the form on the portal, with their login by WhatsApp / SMS"""
        self.ensure_one()
        domain = (self.env.company.institution_portal_email_domain or '').strip().lstrip('@')
        if not domain:
            raise UserError(_("Set the Portal Login Email Domain in the Company settings first."))
        if self.state != 'completed':
            raise UserError(_("Only completed applications can be sent the form."))
        if not self.institution_category:
            raise UserError(_("Select the Institution Type first, it decides which form the donee fills."))
        if not self.institution_type:
            raise UserError(_("Select the Institution Type (Masjid / Madrasa) first, it decides the institution section of the form."))
        if self.institution_category not in FORM_KINDS:
            raise UserError(_("Assistance type is selected through Disbursement Items; choose Masjid or Madrasa as the Institution Type."))
        donee = self.donee_id
        donee_vals = self._portal_donee()
        if len(donee_vals['cnic']) != 13:
            raise UserError(_("Donee %s needs a 13-digit CNIC for the portal.") % donee.name)
        if not donee_vals['whatsapp']:
            raise UserError(_("Donee %s has no mobile number.") % donee.name)

        # One permanent login per donee: later applications reuse it, the portal keeps its password
        login = donee.sadqa_portal_login
        new_login = not login
        if new_login:
            login = self._portal_login_email(domain)
        password = self._generate_portal_password()
        payload = {
            'odooId': self.id,
            'donee': donee_vals,
            'credentials': {'email': login, 'password': password},
            'formKind': FORM_KINDS[self.institution_category],
            'institutionType': self.institution_type,
            'baseInfo': self._portal_base_info(),
        }
        if self.subcategory:
            payload['subCategory'] = self.subcategory
        result = self._portal_call('createApplication', payload) or {}

        if new_login:
            donee.sadqa_portal_login = login
        self.write({
            'state': 'form_sent',
            'portal_application_id': result.get('id') or self.portal_application_id,
            'portal_status': result.get('status'),
        })
        # The application exists on the portal now: a failed message must not undo it
        channel = self._portal_login_channel()
        error = self._send_portal_login(login, password if new_login else _("Use your existing password"))
        if error:
            self.message_post(body=_("⚠️ Form sent on the portal (login %s) but the %s failed: %s. "
                                     "Use Reset Portal Password to send the donee a login.") % (login, channel, error))
            return self._show_notification(_('Send Form'), _('Form sent on the portal, but the %s failed. Use Reset Portal Password.') % channel, 'warning')
        self.message_post(body=_("📨 Form sent on the portal, login %s sent by %s to %s.") % (login, channel, donee.mobile))
        return self._show_notification(_('Send Form'), _('Form sent, the donee got the portal login by %s.') % channel, 'success')

    def action_reset_portal_password(self):
        """resetDoneePassword: new password on the portal, sent to the donee by WhatsApp / SMS"""
        self.ensure_one()
        donee = self.donee_id
        if not donee.sadqa_portal_login:
            raise UserError(_("Donee %s has no portal login yet, use Send Form.") % donee.name)
        password = self._generate_portal_password()
        self._portal_call('resetDoneePassword', {'doneeOdooId': donee.id, 'password': password})
        channel = self._portal_login_channel()
        error = self._send_portal_login(donee.sadqa_portal_login, password)
        if error:
            raise UserError(_("The password was changed on the portal but the %s failed (%s). Reset it again.") % (channel, error))
        self.message_post(body=_("🔑 Portal password reset, login %s sent by %s to %s.") % (donee.sadqa_portal_login, channel, donee.mobile))
        return self._show_notification(_('Reset Portal Password'), _('New password sent to the donee by %s.') % channel, 'success')

    def _acknowledge(self, operation, field_name):
        """acknowledgeDoneeForm / acknowledgeInquiry (idempotent, the portal keeps the first timestamp)"""
        self.ensure_one()
        result = self._portal_call(operation, {'odooId': self.id}) or {}
        acknowledged_at = self.env['sadqa.jariya.fetch.log']._as_datetime(result.get('acknowledgedAt'))
        self[field_name] = acknowledged_at or fields.Datetime.now()

    def action_send_for_inquiry(self):
        """assignOfficer: the inquiry officer gets the application on the portal"""
        self.ensure_one()
        if self.state != 'form_filled':
            raise UserError(_("The donee has to fill the form before it can be sent for inquiry."))
        if not self.line_ids:
            raise UserError(_("Add the Disbursement Items before sending for inquiry."))
        officer = self.employee_id
        if not officer:
            raise UserError(_("Select the Inquiry Officer first."))
        if not officer.active:
            raise UserError(_("Inquiry Officer %s is archived. Reactivate the employee before assigning the inquiry.") % officer.name)
        employee_id = (officer.barcode or '').strip()
        # The portal only assigns an officer once the imported form is acknowledged
        if not self.form_acknowledged_at:
            self._acknowledge('acknowledgeDoneeForm', 'form_acknowledged_at')
        try:
            result = self._portal_call('assignOfficer', {'odooId': self.id, 'employeeId': employee_id}) or {}
        except UserError as error:
            message = str(error).lower()
            if 'bad_request' in message and 'active inquiry officer' in message and 'employee id' in message:
                raise UserError(_(
                    "The portal has no active inquiry officer with employee ID '%(employee_id)s'. "
                    "Add or activate this officer in the portal using the exact Odoo Badge ID, then retry. "
                    "The form is already acknowledged; you do not need to resend it."
                ) % {'employee_id': employee_id}) from error
            raise
        self.write({
            'state': 'send_for_inquiry',
            'portal_report_id': result.get('reportId'),
            'portal_status': 'inquiry_assigned',
        })
        self.message_post(body=_("📤 Sent for inquiry to %s on the portal.") % officer.name)
        return self._show_notification(_('Send for Inquiry'), _('Inquiry officer assigned on the portal.'), 'success')

    @api.model
    def _sync_portal(self, from_cron=False):
        """Import the submitted forms and completed inquiries waiting on the portal, then acknowledge them"""
        Log = self.env['sadqa.jariya.fetch.log']
        if from_cron and not self._portal_configured():
            return Log
        stages = [
            # export, ACK, ACK field, import
            ('getSubmittedForms', 'acknowledgeDoneeForm', 'form_acknowledged_at', Log._import_form_row),
            ('getCompletedInquiries', 'acknowledgeInquiry', 'inquiry_acknowledged_at', Log._import_inquiry_row),
        ]
        counts, errors, applications, to_acknowledge = [0, 0], [], self.browse(), []
        for index, (export, ack, ack_field, import_row) in enumerate(stages):
            for row in self._portal_export(export):
                try:
                    application = self.browse(int(row.get('odooId') or 0)).exists()
                except (TypeError, ValueError):
                    application = self.browse()
                if not application:
                    errors.append(_("%s: no application with Odoo ID %s") % (export, row.get('odooId')))
                    continue
                try:
                    with self.env.cr.savepoint():
                        if import_row(application, row):
                            counts[index] += 1
                except Exception as e:
                    _logger.exception("Sadqa e Jariya %s: %s import failed", application.name, export)
                    errors.append(f"[{application.name}] {export}: {e}")
                    continue
                applications |= application
                to_acknowledge.append((application, ack, ack_field))

        # Imports are saved before the portal is told: an acknowledged row leaves its export
        if not self.env.context.get('sadqa_jariya_no_commit'):
            self.env.cr.commit()
        for application, ack, ack_field in to_acknowledge:
            try:
                with self.env.cr.savepoint():
                    application._acknowledge(ack, ack_field)
            except Exception as e:
                # still exported, acknowledged on the next sync
                errors.append(f"[{application.name}] {ack}: {e}")

        return Log.create({
            'forms_imported': counts[0],
            'inquiries_imported': counts[1],
            'record_ids': [(6, 0, applications.ids)],
            'errors': '\n'.join(errors) or False,
            'sync': not errors,
        })

    def action_check_portal_status(self):
        """Portal Sync, then tell what changed for this application"""
        self.ensure_one()
        state = self.state
        log = self._sync_portal()
        if self.state != state:
            message = _('Form imported, you can now Send for Inquiry.') if self.state == 'form_filled' \
                else _('Inquiry imported, moved to Inquiry Officer.')
            return self._show_notification(_('Check Portal Status'), message, 'success')
        mine = [line for line in (log.errors or '').splitlines() if f"[{self.name}]" in line]
        if mine:
            return self._show_notification(_('Check Portal Status'), '\n'.join(mine), 'danger')
        message = _('The donee has not submitted the form yet.') if state == 'form_sent' \
            else _('The inquiry officer has not completed the inquiry yet.')
        return self._show_notification(_('Check Portal Status'), message, 'warning')
