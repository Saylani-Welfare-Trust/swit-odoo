from odoo import _, models, fields
from odoo.exceptions import UserError, ValidationError


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
    mobile_no = fields.Char('Mobile No.', size=10)
    cnic_no = fields.Char('CNIC No.', size=15)

    country_code_id = fields.Many2one('res.country', string="Country Code")
    microfinance_scheme_id = fields.Many2one('microfinance.scheme', string="Microfinance Scheme")

    search_type = fields.Selection(selection=search_type_selection, string="Search Type", default="registration_id")
    donee_registration_type = fields.Selection(selection=donee_registration_selection, string="Donee Registration Type")
    registration_type = fields.Selection(selection=registration_type_selection, string="Registration Type", default="donee")
    category = fields.Selection(selection=[('individual', 'Individual'), ('institution', 'Institution')], string="Category", default="individual")
    # Programme of a Record Search code (see record.search.program_id)
    program_id = fields.Many2one('res.partner.category', string='Register For')

    # ------------------------------------------------------------------
    # Record Search programmes (tags with a Record Search code)
    # ------------------------------------------------------------------
    def _program(self):
        """The programme tag of this search (empty for the Welfare /
        Microfinance / Medical / Student searches by donee registration type)."""
        return self.program_id

    def _program_search_domain(self):
        if self.search_type == 'registration_id':
            if not self.registration_id:
                raise UserError(_('Please enter the Registration ID to search for.'))
            return [('primary_registration_id', '=', self.registration_id.strip())]
        if self.search_type == 'cnic_no':
            if not self.cnic_no:
                raise UserError(_('Please enter the CNIC No. to search for.'))
            return [('cnic_no', '=', self.cnic_no)]
        if not self.mobile_no:
            raise UserError(_('Please enter the Mobile No. to search for.'))
        domain = [('mobile', '=', self.mobile_no)]
        if self.country_code_id:
            domain.append(('country_code_id', '=', self.country_code_id.id))
        return domain

    def _kind_tag(self):
        program = self._program()
        institution = (program.registration_kind == 'institution'
                       or (program.registration_kind != 'individual' and self.category == 'institution'))
        return self.env.ref('bn_profile_management.coorporate_institute_partner_category' if institution
                            else 'bn_profile_management.individual_partner_category')

    def _search_tags(self):
        """Role and programme tags: every contact found or created gets them."""
        return self.env.ref(ROLE_CATEGORY[self.registration_type]) | self._program()

    def _category_ids(self):
        """Tags of a new profile: role, Individual / Corporate-Institute, programme."""
        if self.registration_type == 'donor':
            return (self._search_tags() | self.env.ref('bn_profile_management.individual_partner_category')).ids
        return (self._search_tags() | self._kind_tag()).ids

    def _form_action(self, partner=None):
        """Profile popup after a programme search: the contact found, or a new
        one with the programme's tags."""
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
            'target': 'new',
            'context': {'from_record_search': True},
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
            action['context']['default_mobile'] = self.mobile_no
        return action

    def _confirm_program(self):
        program = self._program()
        if not program.registration_program_active:
            raise UserError(_('The programme "%s" is disabled.') % program.name)
        # one contact per person: every contact, whatever its tags
        matches = self.env['res.partner'].search(self._program_search_domain())
        if len(matches) > 1:
            raise ValidationError(_("Several contacts match this search. Please refine your search."))
        if matches:
            # a new role / programme ADDS the tags, the person's others stay
            missing = self._search_tags() - matches.category_id
            if missing:
                matches.write({'category_id': [(4, tag.id) for tag in missing]})
        return self._form_action(matches or None)

    def return_donee_form(self, donee=None):
        if self.donee_registration_type == 'microfinance':
            if donee:
                donee.category_id = [(6, 0, [self.env.ref('bn_profile_management.donee_partner_category').id, self.env.ref('bn_profile_management.individual_partner_category').id, self.env.ref('bn_profile_management.microfinance_partner_category').id])]

                self.env.cr.commit()

                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
                    'domain': "[('category_id.name', '=', 'Donee'), ('category_id.name', '=', 'Individual'), ('category_id.name', '=', 'Microfinance')]",
                    'res_id': donee.id,
                    'context': {
                        'microfinance_scheme_id': self.microfinance_scheme_id.id
                    },
                    'target': 'new'
                }
            else:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
                    'domain': "[('category_id.name', '=', 'Donee'), ('category_id.name', '=', 'Individual'), ('category_id.name', '=', 'Microfinance')]",
                    'context': {
                        'default_category_id': [(6, 0, [self.env.ref('bn_profile_management.donee_partner_category').id, self.env.ref('bn_profile_management.individual_partner_category').id, self.env.ref('bn_profile_management.microfinance_partner_category').id])],
                        'default_cnic_no': self.cnic_no,
                        'default_mobile': self.mobile_no,
                        'default_country_code_id': self.country_code_id.id,
                        'microfinance_scheme_id': self.microfinance_scheme_id.id
                    },
                    'target': 'new'
                }
        elif self.donee_registration_type == 'welfare':
            if donee:
                donee.category_id = [(6, 0, [
                                             self.env.ref('bn_profile_management.donee_partner_category').id,
                                             self.env.ref('bn_profile_management.individual_partner_category').id if self.category == 'individual' else self.env.ref('bn_profile_management.coorporate_institute_partner_category').id,
                                             self.env.ref('bn_profile_management.welfare_partner_category').id
                                             ])
                                    ]

                self.env.cr.commit()

                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
                    'domain': '[("category_id.name", "in", ["Donee"])]',
                    'res_id': donee.id,
                    'target': 'new'
                }
            else:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
                    'domain': '[("category_id.name", "in", ["Donee"])]',
                    'context': {
                        'default_category_id': [(6, 0, [
                                             self.env.ref('bn_profile_management.donee_partner_category').id,
                                             self.env.ref('bn_profile_management.individual_partner_category').id if self.category == 'individual' else self.env.ref('bn_profile_management.coorporate_institute_partner_category').id,
                                             self.env.ref('bn_profile_management.welfare_partner_category').id
                                             ])
                                    ],
                        'default_cnic_no': self.cnic_no,
                        'default_mobile': self.mobile_no,
                        'default_country_code_id': self.country_code_id.id,
                        # 'default_scheme_type_ids': [(4, self.scheme_type_id.id)]
                    },
                    'target': 'new'
                }
        elif self.donee_registration_type == 'medical':
            if donee:
                donee.category_id = [(6, 0, [
                                             self.env.ref('bn_profile_management.donee_partner_category').id,
                                             self.env.ref('bn_profile_management.individual_partner_category').id if self.category == 'individual' else self.env.ref('bn_profile_management.coorporate_institute_partner_category').id,
                                             self.env.ref('bn_profile_management.medical_partner_category').id
                                             ])
                                    ]

                self.env.cr.commit()

                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
                    'domain': '[("category_id.name", "in", ["Donee"])]',
                    'res_id': donee.id,
                    'target': 'new'
                }
            else:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
                    'domain': '[("category_id.name", "in", ["Donee"])]',
                    'context': {
                        'default_category_id': [(6, 0, [self.env.ref('bn_profile_management.donee_partner_category').id, self.env.ref('bn_profile_management.individual_partner_category').id, self.env.ref('bn_profile_management.medical_partner_category').id])],
                        'default_cnic_no': self.cnic_no,
                        'default_mobile': self.mobile_no,
                        'default_country_code_id': self.country_code_id.id,
                    },
                    'target': 'new'
                }
        elif self.donee_registration_type == 'student':
            if donee:
                donee.category_id = [(6, 0, [
                                             self.env.ref('bn_profile_management.donee_partner_category').id,
                                             self.env.ref('bn_profile_management.individual_partner_category').id if self.category == 'individual' else self.env.ref('bn_profile_management.coorporate_institute_partner_category').id,
                                             self.env.ref('bn_profile_management.student_partner_category').id
                                             ])
                                    ]

                self.env.cr.commit()

                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
                    'domain': '[("category_id.name", "in", ["Donee"])]',
                    'res_id': donee.id,
                    'target': 'new'
                }
            else:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
                    'domain': '[("category_id.name", "in", ["Donee"])]',
                    'context': {
                        'default_category_id': [(6, 0, [self.env.ref('bn_profile_management.donee_partner_category').id, self.env.ref('bn_profile_management.individual_partner_category').id, self.env.ref('bn_profile_management.student_partner_category').id])],
                        'default_cnic_no': self.cnic_no,
                        'default_mobile': self.mobile_no,
                        'default_country_code_id': self.country_code_id.id,
                    },
                    'target': 'new'
                }

    def action_confirm(self):
        if self._program():
            return self._confirm_program()
        if self.registration_type == 'donee':
            if self.search_type == 'registration_id':
                donee_obj = self.env['res.partner'].search([('primary_registration_id', '=', self.registration_id), ('category_id.name', 'in', ['Donee'])])

                if len(donee_obj) > 1:
                    raise ValidationError("Multiple donee records found with the same mobile number. Please refine your search.")

                if donee_obj:
                    return self.return_donee_form(donee_obj)
                else:
                    return self.return_donee_form()
            elif self.search_type == 'cnic_no':
                donee_obj = self.env['res.partner'].search([('cnic_no', '=', self.cnic_no), ('category_id.name', 'in', ['Donee'])])

                if len(donee_obj) > 1:
                    raise ValidationError("Multiple donee records found with the same mobile number. Please refine your search.")

                if donee_obj:
                    return self.return_donee_form(donee_obj)
                else:
                    return self.return_donee_form()
            elif self.search_type == 'mobile_no':
                donee_obj = self.env['res.partner'].search([('country_code_id', '=', self.country_code_id.id), ('mobile', '=', self.mobile_no), ('category_id.name', 'in', ['Donee'])])

                if len(donee_obj) > 1:
                    raise ValidationError("Multiple donee records found with the same mobile number. Please refine your search.")

                if donee_obj:
                    return self.return_donee_form(donee_obj)
                else:
                    return self.return_donee_form()
        else:
            if self.search_type == 'registration_id':
                donor_obj = self.env['res.partner'].search([('primary_registration_id', '=', self.registration_id), ('category_id.name', 'in', ['Donor'])])

                if len(donor_obj) > 1:
                    raise ValidationError("Multiple donor records found with the same registration ID. Please refine your search.")

                if donor_obj:
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'res.partner',
                        'view_mode': 'form',
                        'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
                        'domain': '[("category_id.name", "in", ["Donor"])]',
                        'res_id': donor_obj.id,
                        'target': 'new'
                    }
                else:
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'res.partner',
                        'view_mode': 'form',
                        'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
                        'domain': '[("category_id.name", "in", ["Donor"])]',
                        'context': {
                            'default_category_id': [(6, 0, [self.env.ref('bn_profile_management.donor_partner_category').id, self.env.ref('bn_profile_management.individual_partner_category').id])]
                        },
                        'target': 'new'
                    }
            elif self.search_type == 'cnic_no':
                donor_obj = self.env['res.partner'].search([('cnic_no', '=', self.cnic_no), ('category_id.name', 'in', ['Donor'])])

                if len(donor_obj) > 1:
                    raise ValidationError("Multiple donor records found with the same registration ID. Please refine your search.")
                
                if donor_obj:
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'res.partner',
                        'view_mode': 'form',
                        'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
                        'domain': '[("category_id.name", "in", ["Donor"])]',
                        'res_id': donor_obj.id,
                        'target': 'new'
                    }
                else:
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'res.partner',
                        'view_mode': 'form',
                        'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
                        'domain': '[("category_id.name", "in", ["Donor"])]',
                        'context': {
                            'default_category_id': [(6, 0, [self.env.ref('bn_profile_management.donor_partner_category').id, self.env.ref('bn_profile_management.individual_partner_category').id])],
                            'default_cnic_no': self.cnic_no
                        },
                        'target': 'new'
                    }
            elif self.search_type == 'mobile_no':
                donor_obj = self.env['res.partner'].search([('phone_code_id', '=', self.phone_code_id.id), ('mobile', '=', self.mobile_no), ('category_id.name', 'in', ['Donor'])])

                if len(donor_obj) > 1:
                    raise ValidationError("Multiple donor records found with the same registration ID. Please refine your search.")
                
                if donor_obj:
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'res.partner',
                        'view_mode': 'form',
                        'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
                        'domain': '[("category_id.name", "in", ["Donor"])]',
                        'res_id': donor_obj.id,
                        'target': 'new'
                    }
                else:
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'res.partner',
                        'view_mode': 'form',
                        'view_id': self.env.ref('bn_profile_management.profile_management_view_form').id,
                        'domain': '[("category_id.name", "in", ["Donor"])]',
                        'context': {
                            'default_category_id': [(6, 0, [self.env.ref('bn_profile_management.donor_partner_category').id, self.env.ref('bn_profile_management.individual_partner_category').id])],
                            'default_mobile': self.mobile_no,
                            'default_country_code_id': self.country_code_id.id,
                        },
                        'target': 'new'
                    }