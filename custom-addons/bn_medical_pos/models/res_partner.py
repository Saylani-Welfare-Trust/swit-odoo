import re

from odoo import _, api, fields, models, Command
from odoo.exceptions import ValidationError
from odoo.osv import expression


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _mh_patient_tags(self):
        """(Donee, Individual, Medical) partner tags"""
        return (
            self.env.ref('bn_profile_management.donee_partner_category'),
            self.env.ref('bn_profile_management.individual_partner_category'),
            self.env.ref('bn_profile_management.medical_patient_partner_category'),
        )

    @api.model
    def _mh_patient_domain(self):
        """Patients: registered donees tagged Medical"""
        donee_tag, _individual_tag, medical_tag = self._mh_patient_tags()
        return [
            ('category_id', 'in', donee_tag.ids),
            ('category_id', 'in', medical_tag.ids),
            ('state', '=', 'register'),
        ]

    @api.model
    def _mh_patient_search_domain(self, term):
        """Patients matching the term on name, mobile, CNIC (with or without dashes) or registration ID"""
        term = (term or '').strip()
        if not term:
            return self._mh_patient_domain()
        term_domains = [
            [('name', 'ilike', term)],
            [('mobile', 'ilike', term)],
            [('cnic_no', 'ilike', term)],
            [('primary_registration_id', 'ilike', term)],
        ]
        digits = re.sub(r'\D', '', term)
        if len(digits) == 13:
            term_domains.append([('cnic_no', '=', self._mh_format_cnic(digits))])
        return expression.AND([self._mh_patient_domain(), expression.OR(term_domains)])

    @api.model
    def _mh_register_patient(self, vals):
        """Register a patient (Donee / Individual / Medical) with name, mobile, CNIC and date of birth.

        A registered donee with the same CNIC is the same person: that profile is tagged
        Medical and returned instead of registering a duplicate.
        Runs as superuser: the counters usually have no rights on donee profiles (see edit_donor_rule).

        :return: (patient, existing)
        """
        name = (vals.get('name') or '').strip()
        mobile = re.sub(r'\D', '', vals.get('mobile') or '')
        if len(mobile) == 11 and mobile.startswith('0'):
            mobile = mobile[1:]
        cnic_digits = re.sub(r'\D', '', vals.get('cnic_no') or '')
        try:
            date_of_birth = fields.Date.to_date(vals.get('date_of_birth') or False)
        except ValueError:
            date_of_birth = False

        if not name:
            raise ValidationError(_("Please enter the patient's name."))
        if not re.fullmatch(r'\d{10}', mobile):
            raise ValidationError(_("Contact number must contain exactly 10 digits."))
        if len(cnic_digits) != 13:
            raise ValidationError(_("CNIC must contain 13 digits (XXXXX-XXXXXXX-X)."))
        if not date_of_birth:
            raise ValidationError(_("Please enter a valid date of birth."))
        if date_of_birth > fields.Date.context_today(self):
            raise ValidationError(_("Date of birth cannot be in the future."))

        cnic_no = self._mh_format_cnic(cnic_digits)
        Partner = self.sudo()
        donee_tag, individual_tag, medical_tag = self._mh_patient_tags()

        existing = Partner.search([
            ('category_id', 'in', donee_tag.ids),
            ('state', '=', 'register'),
            ('cnic_no', '=', cnic_no),
        ], limit=1)
        if existing:
            if medical_tag not in existing.category_id:
                existing.category_id = [Command.link(medical_tag.id)]
            return existing, True

        patient = Partner.create({
            'name': name,
            'mobile': mobile,
            'cnic_no': cnic_no,
            'date_of_birth': date_of_birth,
            'category_id': [Command.set((donee_tag | individual_tag | medical_tag).ids)],
        })
        patient.action_register()
        return patient, False

    @api.model
    def _mh_format_cnic(self, digits):
        return f'{digits[:5]}-{digits[5:12]}-{digits[12:]}'
