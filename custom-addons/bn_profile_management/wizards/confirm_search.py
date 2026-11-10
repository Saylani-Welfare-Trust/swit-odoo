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

ROLE_CATEGORY = {
    'donee': 'bn_profile_management.donee_partner_category',
    'donor': 'bn_profile_management.donor_partner_category',
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
    program_id = fields.Many2one('res.partner.category', string='Register For')
    # several contacts matched: the user picks one
    match_ids = fields.Many2many('res.partner', string='Matching Profiles')

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
        domain = [('mobile', '=', self.env['res.partner']._normalize_mobile(self.mobile_no))]
        if self.country_code_id:
            domain.append(('country_code_id', '=', self.country_code_id.id))
        return domain

    def _program(self):
        """The programme tag (older callers give the donee registration type)."""
        return self.program_id or self.env['res.partner.category']._record_search_program(
            self.donee_registration_type)

    def _kind_tag(self):
        ref = self.env.ref
        program = self._program()
        institution = (program.registration_kind == 'institution'
                       or (program.registration_kind != 'individual' and self.category == 'institution'))
        return (ref('bn_profile_management.coorporate_institute_partner_category') if institution
                else ref('bn_profile_management.individual_partner_category'))

    def _search_tags(self):
        """Role and programme tags: every contact found or created gets them, so
        the programmes (modules) a donee applied to are on the contact."""
        tags = self.env.ref(ROLE_CATEGORY[self.registration_type]) | self._program()
        return tags

    def _category_ids(self):
        """Tags of a new profile: role, Individual / Corporate-Institute, programme."""
        if self.registration_type == 'donor':
            return (self._search_tags() | self.env.ref('bn_profile_management.individual_partner_category')).ids
        return (self._search_tags() | self._kind_tag()).ids

    def _add_search_tags(self, partners):
        """Existing person taking a new role / programme: ADD the tags, never
        replace the ones the person already has. A registered contact then
        shows Register for the new programme."""
        for partner in partners:
            missing = self._search_tags() - partner.category_id
            if missing:
                partner._profile_write({'category_id': [(4, tag.id) for tag in missing]})

    def _layout_tag(self):
        """Form layout after the search: the programme's own (its Profile
        Type form fields, in its order), else the role's."""
        program = self._program()
        if program.is_profile_type and program.profile_form_field_ids:
            return program
        role = self.env.ref(ROLE_CATEGORY[self.registration_type])
        return role if role.is_profile_type else self.env['res.partner.category']

    def _form_action(self, partner=None):
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
            'target': 'new',
            'context': {'from_record_search': True},
        }
        layout = self._layout_tag()
        if layout:
            # the name must end in _view_ref: the web client keeps it for the views
            action['context']['profile_tag_view_ref'] = layout.id
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
            action['context']['default_mobile'] = self.env['res.partner']._normalize_mobile(self.mobile_no)
        return action

    # ------------------------------------------------------------------
    def action_confirm(self):
        self.ensure_one()
        if self.registration_type == 'donee' and not self._program():
            raise UserError(_('Please select what the donee registers for (e.g. Welfare, Microfinance, Medical).'))
        # One contact per person: look at every contact, whatever its tags.
        matches = self.env['res.partner'].search(self._search_domain())
        if len(matches) > 1:
            # Several contacts share this value: the user picks one, which
            # then gets the tags of this search.
            self.match_ids = matches
            return {
                'type': 'ir.actions.act_window',
                'name': _('Matching Profiles'),
                'res_model': 'confirm.search',
                'res_id': self.id,
                'view_mode': 'form',
                'view_id': self.env.ref('bn_profile_management.confirm_search_view_pick').id,
                'target': 'new',
            }
        if matches:
            self._add_search_tags(matches)
        return self._form_action(matches or None)
