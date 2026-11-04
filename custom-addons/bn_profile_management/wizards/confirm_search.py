from odoo import _, fields, models
from odoo.exceptions import UserError


donee_registration_selection = [
    ('student', 'Student'),
    ('welfare', 'Welfare'),
    ('medical', 'Medical'),
    ('microfinance', 'Microfinance'),
]

registration_type_selection = [
    ('donee', 'Donee'),
    ('donor', 'Donor'),
]

search_type_selection = [
    ('registration_id', 'Registration ID'),
    ('cnic_no', 'CNIC No.'),
    ('mobile_no', 'Mobile No.'),
]

# Tag added for each donee programme.
PROGRAM_CATEGORY = {
    'microfinance': 'bn_profile_management.microfinance_partner_category',
    'welfare': 'bn_profile_management.welfare_partner_category',
    'medical': 'bn_profile_management.medical_partner_category',
    'student': 'bn_profile_management.student_partner_category',
}


class ConfirmSearch(models.TransientModel):
    _name = 'confirm.search'
    _description = "Confirm Search"


    registration_id = fields.Char('Registration ID')
    # No size=: it would silently truncate longer input.
    mobile_no = fields.Char('Mobile No.')
    cnic_no = fields.Char('CNIC No.', size=15)

    country_code_id = fields.Many2one('res.country', string="Country Code")

    search_type = fields.Selection(selection=search_type_selection, string="Search Type", default="registration_id")
    donee_registration_type = fields.Selection(selection=donee_registration_selection, string="Donee Registration Type")
    registration_type = fields.Selection(selection=registration_type_selection, string="Registration Type", default="donee")
    category = fields.Selection(selection=[('individual', 'Individual'), ('institution', 'Institution')], string="Category", default="individual")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _search_domain(self):
        """Domain matching the searched value, or an error when it is empty."""
        if self.search_type == 'registration_id':
            if not self.registration_id:
                raise UserError(_('Please enter the Registration ID to search for.'))
            code = self.registration_id.strip()
            return ['|', ('registration_ids.code', '=', code), ('primary_registration_id', '=', code)]
        if self.search_type == 'cnic_no':
            if not self.cnic_no:
                raise UserError(_('Please enter the CNIC No. to search for.'))
            return [('cnic_no', '=', self.cnic_no)]
        if not self.mobile_no:
            raise UserError(_('Please enter the Mobile No. to search for.'))
        domain = [('mobile', '=', self.mobile_no.strip())]
        if self.country_code_id:
            domain.append(('country_code_id', '=', self.country_code_id.id))
        return domain

    def _category_ids(self):
        """Tags of a new profile (and the tags added to an existing one)."""
        ref = self.env.ref
        if self.registration_type == 'donor':
            return [ref('bn_profile_management.donor_partner_category').id,
                    ref('bn_profile_management.individual_partner_category').id]
        kind = (ref('bn_profile_management.individual_partner_category')
                if self.category == 'individual' or self.donee_registration_type == 'microfinance'
                else ref('bn_profile_management.coorporate_institute_partner_category'))
        return [ref('bn_profile_management.donee_partner_category').id, kind.id,
                ref(PROGRAM_CATEGORY[self.donee_registration_type]).id]

    def _form_action(self, partner=None):
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
            'target': 'new',
            'context': {},
        }
        if partner:
            action['res_id'] = partner.id
            return action
        action['context'].update({
            'default_category_id': [(6, 0, self._category_ids())],
            'default_country_code_id': (self.country_code_id or self.env.ref('base.pk')).id,
        })
        if self.cnic_no:
            action['context']['default_cnic_no'] = self.cnic_no
        if self.mobile_no:
            action['context']['default_mobile'] = self.mobile_no.strip()
        return action

    def _list_action(self, partners):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Matching Profiles'),
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'views': [(self.env.ref('bn_profile_management.profile_management_view_tree').id, 'tree'),
                      (self.env.ref('bn_profile_management.profile_management_view_form').id, 'form')],
            'domain': [('id', 'in', partners.ids)],
            'target': 'current',
        }

    # ------------------------------------------------------------------
    def action_confirm(self):
        self.ensure_one()
        if self.registration_type == 'donee' and not self.donee_registration_type:
            raise UserError(_('Please select the Donee Registration Type (Student, Welfare, Medical or Microfinance).'))
        # One contact per person: look at every contact, whatever its tags.
        matches = self.env['res.partner'].search(self._search_domain())
        if len(matches) > 1:
            # Several contacts share this value: let the user pick one.
            return self._list_action(matches)
        if matches:
            # Existing person taking a new role / programme: ADD the role and
            # programme tags, never replace the ones the person already has.
            # A registered contact then shows Register for the new role.
            ref = self.env.ref
            if self.registration_type == 'donor':
                new_tags = [ref('bn_profile_management.donor_partner_category').id]
            else:
                new_tags = [ref('bn_profile_management.donee_partner_category').id,
                            ref(PROGRAM_CATEGORY[self.donee_registration_type]).id]
            missing = [tid for tid in new_tags if tid not in matches.category_id.ids]
            if missing:
                matches._profile_write({'category_id': [(4, tid) for tid in missing]})
        return self._form_action(matches or None)
