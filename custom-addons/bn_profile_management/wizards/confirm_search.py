from odoo import models, fields
from odoo.exceptions import ValidationError


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


class ConfirmSearch(models.TransientModel):
    _name = 'confirm.search'
    _description = "Confirm Search"


    registration_id = fields.Char('Registration ID')
    mobile_no = fields.Char('Mobile No.', size=10)
    cnic_no = fields.Char('CNIC No.', size=13)

    country_code_id = fields.Many2one('res.country', string="Country Code")

    search_type = fields.Selection(selection=search_type_selection, string="Search Type", default="registration_id")
    donee_registration_type = fields.Selection(selection=donee_registration_selection, string="Donee Registration Type")
    registration_type = fields.Selection(selection=registration_type_selection, string="Registration Type", default="donee")


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
                        # 'default_scheme_type_ids': [(4, self.scheme_type_id.id)]
                    },
                    'target': 'new'
                }
        elif self.donee_registration_type == 'welfare':
            if donee:
                donee.category_id = [(6, 0, [self.env.ref('bn_profile_management.donee_partner_category').id, self.env.ref('bn_profile_management.individual_partner_category').id, self.env.ref('bn_profile_management.welfare_partner_category').id])]

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
                        'default_category_id': [(6, 0, [self.env.ref('bn_profile_management.donee_partner_category').id, self.env.ref('bn_profile_management.individual_partner_category').id, self.env.ref('bn_profile_management.welfare_partner_category').id])],
                        'default_cnic_no': self.cnic_no,
                        'default_mobile': self.mobile_no,
                        'default_country_code_id': self.country_code_id.id,
                        # 'default_scheme_type_ids': [(4, self.scheme_type_id.id)]
                    },
                    'target': 'new'
                }
        elif self.donee_registration_type == 'medical':
            if donee:
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
        if self.registration_type == 'donee':
            if self.search_type == 'registration_id':
                donee_obj = self.env['res.partner'].search([('primary_registration_id', '=', self.registration_id), ('category_id.name', 'in', ['Donee'])])

                if donee_obj:
                    return self.return_donee_form(donee_obj)
                else:
                    return self.return_donee_form()
            elif self.search_type == 'cnic_no':
                donee_obj = self.env['res.partner'].search([('cnic_no', '=', self.cnic_no), ('category_id.name', 'in', ['Donee'])])

                if donee_obj:
                    return self.return_donee_form(donee_obj)
                else:
                    return self.return_donee_form()
            elif self.search_type == 'mobile_no':
                donee_obj = self.env['res.partner'].search([('country_code_id', '=', self.country_code_id.id), ('mobile', '=', self.mobile_no), ('category_id.name', 'in', ['Donee'])])

                if donee_obj:
                    return self.return_donee_form(donee_obj)
                else:
                    return self.return_donee_form()
        else:
            if self.search_type == 'registration_id':
                donor_obj = self.env['res.partner'].search([('primary_registration_id', '=', self.registration_id), ('category_id.name', 'in', ['Donor'])])

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