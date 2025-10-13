from odoo import fields, models, api, exceptions, _

import re

# CNIC regular expression
cnic_pattern = r'^\d{5}-\d{7}-\d{1}$'
# Regular expression for mobile number (with optional country code)
# mobile_pattern = r'^\+?[1-9]\d{1,14}$|^\d{11}$'
# mobile_pattern = r'^\+?[1-9]\d{1,14}$|^\+?[1-9]\d{1,14}(\s?\d+)+$|^\d{11}$'
mobile_pattern = r"^(?:\+92|92|0)[\s-]?[3-9][0-9]{2}[\s-]?[0-9]{7}$"

donee_registration_selection = [
    ('student', 'Student'),
    ('welfare', 'Welfare'),
    ('employee', 'Employee'),
    ('microfinance', 'MicroFinance'),
    ('medical', 'Medical'),
]

person_type_selection = [
    ('donee', 'Donee'),
    ('donor', 'Donor'),
]

search_type_selection = [
    ('registration_id', 'Registration ID'),
    ('cnic_no', 'CNIC No.'),
    ('mobile_no', 'Mobile No.'),
]

# microfinance_application_selection = [
#     ('asan_qarz', 'Asan Qarz'),
#     ('asan_karobar',  'Asan Karobar'),
#     ('rickshaw', 'Rickshaw'),
#     ('motor_cycle', 'Motor Cycle'),
#     ('housing', 'Housing'),
#     ('laptop', 'Laptop'),
#     ('mobile', 'Mobile'),
# ]

# welfare_application_selection = [
#     ('madad_kifalat', 'Madad / Kifalat'),
# ]


class SearchRecord(models.TransientModel):
    _name = 'search.record'


    registration_id = fields.Char('Registration ID')
    mobile_no = fields.Char('Mobile No.', size=10)
    cnic_no = fields.Char('CNIC No.', size=15)
    
    phone_code_id = fields.Many2one('res.country', string="Phone Code ID")

    search_type = fields.Selection(selection=search_type_selection, string="Search Type", default="registration_id")
    person_type = fields.Selection(selection=person_type_selection, string="Person Type", default="donee")
    donee_registration_type = fields.Selection(selection=donee_registration_selection, string="Donee Registration Type")
    
    # welfare_application_type = fields.Selection(selection=welfare_application_selection, string="Application Type")
    # microfinance_application_type = fields.Selection(selection=microfinance_application_selection, string="Application Type")

    @api.constrains('cnic_no')
    def _check_cnic_format(self):
        for record in self:
            if record.cnic_no:
                if not re.match(r'^\d{5}-\d{7}-\d{1}$', record.cnic_no):
                    raise exceptions.ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.cnic_no.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise exceptions.ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")

    @api.onchange('cnic_no')
    def _onchange_cnic_no(self):
        if self.cnic_no and self.search_type == 'cnic_no':
            cleaned_cnic = re.sub(r'[^0-9]', '', self.cnic_no)
            if len(cleaned_cnic) >= 13:
                self.cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:12]}-{cleaned_cnic[12:]}"
            elif len(cleaned_cnic) > 5:
                self.cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:]}"

    def action_search(self):
        if self.cnic_no and not re.match(cnic_pattern, self.cnic_no):
            raise exceptions.ValidationError(str(f'Invalid CNIC No. {self.cnic_no}'))

        return {
            'type': 'ir.actions.act_window',
            'name': 'Confirmation',
            'res_model': 'confirm.search',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_profile_search.confirm_search_view_form').id,
            'context': {
                'default_search_type': self.search_type,
                'default_registration_id': self.registration_id,
                'default_phone_code_id': self.phone_code_id.id,
                'default_mobile_no': self.mobile_no,
                'default_cnic_no': self.cnic_no,
                'default_person_type': self.person_type,
                'default_donee_registration_type': self.donee_registration_type,
                'default_scheme_type_id': self.scheme_type_id.id,
                # 'default_disbursement_type_ids': [(4, self.disbursement_type_id.id)],
            },
            'target': 'new',
        }

    def return_donee_form(self, donee=None):
        if self.donee_registration_type == 'microfinance':
            if donee:
                donee.scheme_type_ids = [(4, self.scheme_type_id.id)]
                donee.is_microfinance = True

                self.env.cr.commit()

                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.custom_donee_res_partner_view_form').id,
                    'res_id': donee.id,
                    'context': {
                        'default_is_donee': True,
                        'default_donee_type': 'individual',
                        'default_is_microfinance': True,
                        'default_registration_category': 'donee',
                        'default_scheme_type_ids': [(4, self.scheme_type_id.id)],
                        # 'default_disbursement_type_ids': [(4, self.disbursement_type_id.id)],
                    },
                }
            else:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.custom_donee_res_partner_view_form').id,
                    'context': {
                        'default_is_donee': True,
                        'default_donee_type': 'individual',
                        'default_is_microfinance': True,
                        'default_registration_category': 'donee',
                        'default_cnic_no': self.cnic_no,
                        'default_mobile': self.mobile_no,
                        'default_scheme_type_ids': [(4, self.scheme_type_id.id)],
                        # 'default_disbursement_type_ids': [(4, self.disbursement_type_id.id)],
                    },
                }
        elif self.donee_registration_type == 'welfare':
            if donee:
                # donee.disbursement_type_ids = [(4, self.disbursement_type_id.id)]
                donee.is_welfare = True

                self.env.cr.commit()

                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.custom_donee_res_partner_view_form').id,
                    'res_id': donee.id,
                    'context': {
                        'default_is_donee': True,
                        'default_donee_type': 'individual',
                        'default_is_welfare': True,
                        'default_registration_category': 'donee',
                        'default_scheme_type_ids': [(4, self.scheme_type_id.id)],
                        # 'default_disbursement_type_ids': [(4, self.disbursement_type_id.id)],
                    },
                }
            else:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.custom_donee_res_partner_view_form').id,
                    'context': {
                        'default_is_donee': True,
                        'default_donee_type': 'individual',
                        'default_is_welfare': True,
                        'default_registration_category': 'donee',
                        'default_cnic_no': self.cnic_no,
                        'default_mobile': self.mobile_no,
                        'default_scheme_type_ids': [(4, self.scheme_type_id.id)],
                        # 'default_disbursement_type_ids': [(4, self.disbursement_type_id.id)],
                    },
                }
        elif self.donee_registration_type == 'medical':
            if donee:
                donee.is_medical = True

                self.env.cr.commit()

                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.custom_donee_res_partner_view_form').id,
                    'res_id': donee.id,
                    'context': {
                        'default_is_donee': True,
                        'default_donee_type': 'individual',
                        'default_is_medical': True,
                        'default_registration_category': 'donee',
                    },
                }
            else:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.custom_donee_res_partner_view_form').id,
                    'context': {
                        'default_is_donee': True,
                        'default_donee_type': 'individual',
                        'default_is_medical': True,
                        'default_registration_category': 'donee',
                        'default_cnic_no': self.cnic_no,
                        'default_mobile': self.mobile_no,
                    },
                }
        elif self.donee_registration_type == 'student':
            if donee:
                donee.is_student = True

                self.env.cr.commit()

                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.custom_donee_res_partner_view_form').id,
                    'res_id': donee.id,
                    'context': {
                        'default_is_donee': True,
                        'default_donee_type': 'individual',
                        'default_is_student': True,
                        'default_registration_category': 'donee',
                    },
                }
            else:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.custom_donee_res_partner_view_form').id,
                    'context': {
                        'default_is_donee': True,
                        'default_donee_type': 'individual',
                        'default_is_student': True,
                        'default_registration_category': 'donee',
                        'default_cnic_no': self.cnic_no,
                        'default_mobile': self.mobile_no,
                    },
                }
        elif self.donee_registration_type == 'employee':
            if donee:
                donee.is_employee = True

                self.env.cr.commit()

                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.custom_donee_res_partner_view_form').id,
                    'res_id': donee.id,
                    'context': {
                        'default_is_donee': True,
                        'default_donee_type': 'individual',
                        'default_is_employee': True,
                        'default_registration_category': 'donee',
                    },
                }
            else:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'form',
                    'view_id': self.env.ref('bn_profile_management.custom_donee_res_partner_view_form').id,
                    'context': {
                        'default_is_donee': True,
                        'default_donee_type': 'individual',
                        'default_is_employee': True,
                        'default_registration_category': 'donee',
                        'default_cnic_no': self.cnic_no,
                        'default_mobile': self.mobile_no,
                    },
                }

    def action_search_registration(self):
        if self.cnic_no and not re.match(cnic_pattern, self.cnic_no):
            raise exceptions.ValidationError(str(f'Invalid CNIC No. {self.cnic_no}'))

        if self.person_type == 'donee':
            if self.search_type == 'registration_id':
                donee_obj = self.env['res.partner'].search([('barcode', '=', self.registration_id), ('is_donee', '=', True), ('registration_category', '=', 'donee')])

                if donee_obj:
                    return self.return_donee_form(donee_obj)
                else:
                    return self.return_donee_form()
                    
            elif self.search_type == 'cnic_no':
                donee_obj = self.env['res.partner'].search([('cnic_no', '=', self.cnic_no), ('is_donee', '=', True), ('registration_category', '=', 'donee')])

                if donee_obj:
                    return self.return_donee_form(donee_obj)
                else:
                    return self.return_donee_form()
            elif self.search_type == 'mobile_no':
                donee_obj = self.env['res.partner'].search([('phone_code_id', '=', self.phone_code_id.id), ('mobile', '=', self.mobile_no), ('is_donee', '=', True), ('registration_category', '=', 'donee')])

                if donee_obj:
                    return self.return_donee_form(donee_obj)
                else:
                    return self.return_donee_form()
        else:
            if self.search_type == 'registration_id':
                donor_obj = self.env['res.partner'].search([('barcode', '=', self.registration_id), ('is_donee', '=', False), ('registration_category', '=', 'donor')])

                if donor_obj:
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'res.partner',
                        'view_mode': 'form',
                        'view_id': self.env.ref('bn_profile_management.custom_donor_res_partner_view_form').id,
                        'res_id': donor_obj.id,
                        'context': {
                            'default_is_donee': False,
                            'default_donor_type': 'individual',
                            'default_registration_category': 'donor',
                            'default_cnic_no': self.cnic_no,
                            'default_mobile': self.mobile_no,
                        },
                    }
                else:
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'res.partner',
                        'view_mode': 'form',
                        'view_id': self.env.ref('bn_profile_management.custom_donor_res_partner_view_form').id,
                        'context': {
                            'default_is_donee': False,
                            'default_donor_type': 'individual',
                            'default_registration_category': 'donor',
                            'default_cnic_no': self.cnic_no,
                            'default_mobile': self.mobile_no,
                        },
                    }
                    
            elif self.search_type == 'cnic_no':
                donor_obj = self.env['res.partner'].search([('cnic_no', '=', self.cnic_no), ('is_donee', '=', False), ('registration_category', '=', 'donor')])

                if donor_obj:
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'res.partner',
                        'view_mode': 'form',
                        'view_id': self.env.ref('bn_profile_management.custom_donor_res_partner_view_form').id,
                        'res_id': donor_obj.id,
                        'context': {
                            'default_is_donee': False,
                            'default_donor_type': 'individual',
                            'default_registration_category': 'donor',
                            'default_cnic_no': self.cnic_no,
                            'default_mobile': self.mobile_no,
                        },
                    }
                else:
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'res.partner',
                        'view_mode': 'form',
                        'view_id': self.env.ref('bn_profile_management.custom_donor_res_partner_view_form').id,
                        'context': {
                            'default_is_donee': False,
                            'default_donor_type': 'individual',
                            'default_registration_category': 'donor',
                            'default_cnic_no': self.cnic_no,
                            'default_mobile': self.mobile_no,
                        },
                    }
            elif self.search_type == 'mobile_no':
                donor_obj = self.env['res.partner'].search([('phone_code_id', '=', self.phone_code_id.id), ('mobile', '=', self.mobile_no), ('is_donee', '=', False), ('registration_category', '=', 'donor')])

                if donor_obj:
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'res.partner',
                        'view_mode': 'form',
                        'view_id': self.env.ref('bn_profile_management.custom_donor_res_partner_view_form').id,
                        'res_id': donor_obj.id,
                        'context': {
                            'default_is_donee': False,
                            'default_donor_type': 'individual',
                            'default_registration_category': 'donor',
                            'default_cnic_no': self.cnic_no,
                            'default_mobile': self.mobile_no,
                        },
                    }
                else:
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'res.partner',
                        'view_mode': 'form',
                        'view_id': self.env.ref('bn_profile_management.custom_donor_res_partner_view_form').id,
                        'context': {
                            'default_is_donee': False,
                            'default_donor_type': 'individual',
                            'default_registration_category': 'donor',
                            'default_cnic_no': self.cnic_no,
                            'default_mobile': self.mobile_no,
                        },
                    }