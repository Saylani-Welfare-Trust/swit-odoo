import base64
import logging
from urllib.parse import urlparse

import requests

from odoo import models, fields, _
from odoo.exceptions import UserError

from .sadqa_jariya import FORM_KINDS
from .sadqa_jariya_form import PHOTO_DOCUMENT_TYPES

_logger = logging.getLogger(__name__)

# Contact person's picture in a submitted row, becomes the donee's picture
# (not in the contract yet: profileImage is the old portal's donee photo)
PICTURE_KEYS = ('contactPersonImage', 'profileImage')

# portal formKind -> institution type
FORM_KIND_CATEGORIES = {form_kind: category for category, form_kind in FORM_KINDS.items()}
LEGACY_FORM_KINDS = {'construction', 'flood-institute'}


class SadqaJariyaFetchLog(models.Model):
    _name = 'sadqa.jariya.fetch.log'
    _description = 'Sadqa e Jariya Portal Sync Log'
    _order = 'fetch_date desc'

    fetch_date = fields.Datetime('Sync Date', default=fields.Datetime.now, readonly=True)
    forms_imported = fields.Integer('Forms Imported', readonly=True)
    inquiries_imported = fields.Integer('Inquiries Imported', readonly=True)
    record_ids = fields.Many2many('sadqa.jariya', 'sadqa_jariya_fetch_log_rel', 'log_id', 'application_id', string='Applications')
    errors = fields.Text('Errors', readonly=True)
    sync = fields.Boolean('All Imported', readonly=True)

    def _as_bool(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in ['yes', 'true', '1', 'y', 't']
        return False

    def _as_float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _as_int(self, value):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    def _as_date(self, value):
        try:
            return fields.Date.to_date(value) or False
        except (TypeError, ValueError):
            return False

    def _as_datetime(self, value):
        """Portal dates are ISO (2025-10-03T05:52:17.584Z)"""
        if not isinstance(value, str):
            return False
        try:
            return fields.Datetime.to_datetime(value.replace('T', ' ')[:19])
        except ValueError:
            return False

    def action_view_fetched_records(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Synced Applications'),
            'res_model': 'sadqa.jariya',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.record_ids.ids)],
            'target': 'current',
        }

    def _portal_form_vals(self, form):
        """sadqa.jariya.form values of a portal form (flat camelCase keys), only the keys sent"""
        Model = self.env['sadqa.jariya.form']
        vals = {}
        for key, field_name in Model._portal_form_fields.items():
            if key not in form:
                continue
            value = form[key]
            field_type = Model._fields[field_name].type
            if field_type == 'integer':
                value = self._as_int(value)
            elif field_type == 'float':
                value = self._as_float(value)
            elif field_type == 'boolean':
                value = self._as_bool(value)
            elif field_type == 'date':
                value = self._as_date(value)
            else:
                value = str(value) if value not in (None, False) else False
            vals[field_name] = value
        return vals

    def _portal_photo_documents(self, application, submission, form):
        """Documents of the form's photos (signed URLs valid 15 minutes): a failed download fails the import,
        the row is not acknowledged and the next sync gets fresh URLs"""
        vals_list = []
        for key, (document_type, _label) in PHOTO_DOCUMENT_TYPES.items():
            value = form.get(key)
            if not value:
                continue
            try:
                data = self._portal_picture(value)
            except Exception as e:
                raise UserError(_("Photo %(photo)s could not be downloaded (%(error)s); the form is imported again on the next sync.",
                                  photo=key, error=e)) from e
            url = value.get('url') if isinstance(value, dict) else value
            filename = urlparse(url).path.rsplit('/', 1)[-1] if isinstance(url, str) and url.startswith('http') else ''
            vals_list.append({
                'application_id': application.id,
                'document_type': document_type,
                'image_data': data,
                'image_filename': filename or f'{document_type}.jpg',
                'uploaded_from': submission,
            })
        return vals_list

    def _create_portal_form(self, application, submission, form, row, submitted_at, report=None):
        institution_type = row.get('institutionType')
        # the photos go to the application's Documents (viewed, removed and added to there)
        photo_documents = self._portal_photo_documents(application, submission, form)
        portal_form = self.env['sadqa.jariya.form'].create(dict(
            self._portal_form_vals(form),
            application_id=application.id,
            submission=submission,
            form_kind=row.get('formKind'),
            report_id=report.id if report else False,
            institution_type=institution_type if institution_type in ('masjid', 'madrasa') else application.institution_type,
            submitted_at=self._as_datetime(submitted_at),
        ))
        self.env['sadqa.jariya.document'].create([dict(vals, form_id=portal_form.id) for vals in photo_documents])

    def _import_form_row(self, application, row):
        """Submitted form of a getSubmittedForms row, True when imported now (False: imported before)"""
        form_kind = row.get('formKind')
        category = FORM_KIND_CATEGORIES.get(form_kind)
        if not category and form_kind in LEGACY_FORM_KINDS:
            category = row.get('institutionType') or application.institution_type
        category = category or application.institution_category
        if category not in FORM_KINDS:
            raise UserError(_("Unknown form kind %s") % row.get('formKind'))
        if application.donee_form_id:
            return False

        form = row.get('form') or {}
        base_info = row.get('baseInfo') or {}
        vals = {
            'institution_category': category,
            'portal_application_id': row.get('id') or application.portal_application_id,
            'portal_status': row.get('status'),
            'subcategory': row.get('subCategory') or application.subcategory,
        }
        if row.get('institutionType') in ('masjid', 'madrasa'):
            vals['institution_type'] = row['institutionType']
        for key, field_name in (('institutionName', 'institute_name'), ('institutionAddress', 'address'), ('accountTitle', 'account_title'),
                                ('accountNumber', 'account_number'), ('applicantLocationLink', 'applicant_location_link')):
            value = form.get(key) if form.get(key) not in (None, '') else base_info.get(key)
            # account details entered in Odoo before Complete are kept; the donee's stay on the Donee Form tab
            if field_name in ('account_title', 'account_number') and application[field_name]:
                continue
            if value not in (None, ''):
                vals[field_name] = str(value)
        if application.state in ('completed', 'form_sent'):
            vals['state'] = 'form_filled'
        application.write(vals)

        self._create_portal_form(application, 'donee', form, row, row.get('submittedAt'))
        application.message_post(body=_("📝 Form submitted by the donee on the portal (%s), imported.")
                                 % (row.get('submittedAt') or '').replace('T', ' ')[:16])
        self._import_donee_picture(application.donee_id, row)
        return True

    def _portal_picture(self, value):
        """base64 of a portal picture: URL, data URL or plain base64"""
        if isinstance(value, dict):
            value = value.get('url') or value.get('data')
        if not isinstance(value, str) or not value.strip():
            return False
        value = value.strip()
        if value.startswith('http'):
            response = requests.get(value, timeout=20)
            response.raise_for_status()
            return base64.b64encode(response.content)
        if value.startswith('data:') and ',' in value:
            value = value.split(',', 1)[1]
        base64.b64decode(value, validate=True)
        return value.encode()

    def _import_donee_picture(self, donee, row):
        """The contact person's picture, if the portal sent one, becomes the donee's picture"""
        for source in (row.get('form') or {}, row.get('baseInfo') or {}, row):
            for key in PICTURE_KEYS:
                if not source.get(key):
                    continue
                try:
                    with self.env.cr.savepoint():
                        picture = self._portal_picture(source[key])
                        if picture:
                            donee.image_1920 = picture
                            return True
                except Exception as e:
                    # a bad picture must not stop the form import
                    _logger.warning("Sadqa e Jariya donee %s: portal picture %s not imported: %s", donee.id, key, e)
        return False

    def _import_inquiry_row(self, application, row):
        """Completed inquiry of a getCompletedInquiries row, True when imported now (False: imported before)"""
        inquiry = row.get('inquiry') or {}
        if application._portal_row_imported(row):
            return False
        officer = inquiry.get('officer') or {}
        code = officer.get('employeeId')
        employee = self.env['hr.employee'].search([('barcode', '=', code)], limit=1) if code else self.env['hr.employee']
        report = self.env['sadqa.jariya.inquiry.report'].create({
            'application_id': application.id,
            'external_id': inquiry.get('id'),
            'status': 'completed',
            'content': inquiry.get('remarks'),
            'officer_id': employee.id,
            'officer_name': officer.get('name'),
            'officer_employee_code': code,
            'report_date': self._as_datetime(inquiry.get('completedAt')),
        })
        # the officer's own completed form and photos (null for applications made before the three-section forms)
        if isinstance(inquiry.get('form'), dict):
            self._create_portal_form(application, 'officer', inquiry['form'], row, inquiry.get('completedAt'), report)
        vals = {'portal_status': row.get('status')}
        if application.state in ('form_filled', 'send_for_inquiry'):
            vals['state'] = 'inquiry'
        application.write(vals)
        application.message_post(body=_("🔎 Inquiry completed on the portal by %s, imported.") % (officer.get('name') or ''))
        return True
