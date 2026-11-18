import re

from odoo import _, fields, models, Command
from odoo.exceptions import AccessError, ValidationError
from odoo.osv import expression


class POSSession(models.Model):
    _inherit = 'pos.session'


    def _loader_params_product_product(self):
        result = super()._loader_params_product_product()
        result['search_params']['fields'].append('is_medical_equipment')
        return result

    # ------------------------------------------------------------------
    # Register Patient (POS action)
    # Cashiers usually have no rights on donee profiles (see edit_donor_rule),
    # so these run as superuser, gated on the POS group.
    # ------------------------------------------------------------------

    def _check_patient_pos_access(self):
        if not self.env.user.has_group('bn_medical_equipment.medical_patient_pos_action_group'):
            raise AccessError(_("You are not allowed to register patients from the Point of Sale."))

    def _patient_tags(self):
        """(Donee, Individual, Medical) partner tags"""
        return (
            self.env.ref('bn_profile_management.donee_partner_category'),
            self.env.ref('bn_profile_management.individual_partner_category'),
            self.env.ref('bn_profile_management.medical_patient_partner_category'),
        )

    def _patient_pos_data(self, partners):
        """Partners as the POS loads them, plus what the patient popup shows"""
        fields_list = self._loader_params_res_partner()['search_params']['fields']
        extra = ['mobile', 'cnic_no', 'primary_registration_id', 'date_of_birth']
        return partners.read(list(dict.fromkeys(fields_list + extra)))

    def pos_search_medical_patients(self, term='', limit=20):
        """Registered donees tagged Medical, matching the term on name, mobile, CNIC or registration ID"""
        self.ensure_one()
        self._check_patient_pos_access()
        donee_tag, _individual_tag, medical_tag = self._patient_tags()

        domain = [
            ('category_id', 'in', donee_tag.ids),
            ('category_id', 'in', medical_tag.ids),
            ('state', '=', 'register'),
        ]
        term = (term or '').strip()
        if term:
            term_domains = [
                [('name', 'ilike', term)],
                [('mobile', 'ilike', term)],
                [('cnic_no', 'ilike', term)],
                [('primary_registration_id', 'ilike', term)],
            ]
            digits = re.sub(r'\D', '', term)
            if len(digits) == 13:
                # CNIC typed without dashes
                term_domains.append([('cnic_no', '=', self._format_cnic(digits))])
            domain = expression.AND([domain, expression.OR(term_domains)])

        patients = self.env['res.partner'].sudo().search(domain, limit=limit, order='name, id' if term else 'id desc')
        return self._patient_pos_data(patients)

    def pos_register_medical_patient(self, vals):
        """Register a patient (Donee / Individual / Medical) from the POS.

        A registered donee with the same CNIC is the same person, so that profile
        is tagged Medical and returned instead of registering a duplicate.
        """
        self.ensure_one()
        self._check_patient_pos_access()

        name = (vals.get('name') or '').strip()
        mobile = (vals.get('mobile') or '').strip()
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

        cnic_no = self._format_cnic(cnic_digits)
        Partner = self.env['res.partner'].sudo()
        donee_tag, individual_tag, medical_tag = self._patient_tags()

        existing = Partner.search([
            ('category_id', 'in', donee_tag.ids),
            ('state', '=', 'register'),
            ('cnic_no', '=', cnic_no),
        ], limit=1)
        if existing:
            if medical_tag not in existing.category_id:
                existing.category_id = [Command.link(medical_tag.id)]
            return {'existing': True, 'partner': self._patient_pos_data(existing)[0]}

        patient = Partner.create({
            'name': name,
            'mobile': mobile,
            'cnic_no': cnic_no,
            'date_of_birth': date_of_birth,
            'category_id': [Command.set((donee_tag | individual_tag | medical_tag).ids)],
        })
        patient.action_register()
        return {'existing': False, 'partner': self._patient_pos_data(patient)[0]}

    @staticmethod
    def _format_cnic(digits):
        return f'{digits[:5]}-{digits[5:12]}-{digits[12:]}'
