import base64
import logging

import requests

from odoo import models, fields, _
from odoo.exceptions import UserError

from .sadqa_jariya import FORM_KINDS, FORM_HEADER_KEYS, FORM_DETAIL_FIELDS

_logger = logging.getLogger(__name__)

# Contact person's picture in a submitted row, becomes the donee's picture
# (not in the contract yet: profileImage is the old portal's donee photo)
PICTURE_KEYS = ('contactPersonImage', 'profileImage')

# portal formKind -> institution_category
FORM_KIND_CATEGORIES = {form_kind: category for category, form_kind in FORM_KINDS.items()}


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

    def _portal_form_vals(self, model_name, form):
        """Values of a detail model for the form keys it maps in _portal_form_fields, only the keys sent"""
        Model = self.env[model_name]
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

    def _import_form_row(self, application, row):
        """Submitted form of a getSubmittedForms row, True when imported now (False: imported before)"""
        category = FORM_KIND_CATEGORIES.get(row.get('formKind')) or application.institution_category
        if category not in FORM_DETAIL_FIELDS:
            raise UserError(_("Unknown form kind %s") % row.get('formKind'))
        application.institution_category = category
        if application._form_details():
            return False

        form = row.get('form') or {}
        name_key, address_key = FORM_HEADER_KEYS[category]
        vals = {
            'portal_application_id': row.get('id') or application.portal_application_id,
            'portal_status': row.get('status'),
            'subcategory': row.get('subCategory') or application.subcategory,
        }
        for key, field_name in ((name_key, 'institute_name'), (address_key, 'address'), ('accountTitle', 'account_title'),
                                ('accountNumber', 'account_number'), ('applicantLocationLink', 'applicant_location_link')):
            if form.get(key) not in (None, ''):
                vals[field_name] = str(form[key])
        if application.state in ('completed', 'form_sent'):
            vals['state'] = 'form_filled'
        application.write(vals)

        detail_model = application._fields[FORM_DETAIL_FIELDS[category]].comodel_name
        self.env[detail_model].create(dict(self._portal_form_vals(detail_model, form), application_id=application.id))
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
        if inquiry.get('id') and inquiry['id'] in application.inquiry_report_ids.mapped('external_id'):
            return False
        officer = inquiry.get('officer') or {}
        code = officer.get('employeeId')
        employee = self.env['hr.employee'].search([('barcode', '=', code)], limit=1) if code else self.env['hr.employee']
        self.env['sadqa.jariya.inquiry.report'].create({
            'application_id': application.id,
            'external_id': inquiry.get('id'),
            'status': 'completed',
            'content': inquiry.get('remarks'),
            'officer_id': employee.id,
            'officer_name': officer.get('name'),
            'officer_employee_code': code,
            'report_date': self._as_datetime(inquiry.get('completedAt')),
        })
        vals = {'portal_status': row.get('status')}
        if application.state in ('form_filled', 'send_for_inquiry'):
            vals['state'] = 'inquiry'
        application.write(vals)
        application.message_post(body=_("🔎 Inquiry completed on the portal by %s, imported.") % (officer.get('name') or ''))
        return True
