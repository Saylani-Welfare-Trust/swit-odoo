from odoo import models, fields, api
from odoo.exceptions import ValidationError

import re

cnic_pattern = r'^\d{5}-\d{7}-\d{1}$'


donee_registration_selection = [
    ('student', 'Student'),
    ('welfare', 'Welfare'),
    ('microfinance', 'MicroFinance'),
    ('medical', 'Medical'),
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


class RecordSearch(models.TransientModel):
    _name = 'record.search'
    _description = "Record Search"


    registration_id = fields.Char('Registration ID')
    mobile_no = fields.Char('Mobile No.', size=10)
    cnic_no = fields.Char('CNIC No.')
    
    country_code_id = fields.Many2one('res.country', string="Country Code")

    search_type = fields.Selection(selection=search_type_selection, string="Search Type", default="registration_id")
    donee_registration_type = fields.Selection(selection=donee_registration_selection, string="Donee Registration Type")
    registration_type = fields.Selection(selection=registration_type_selection, string="Registration Type", default="donee")


    @api.constrains('cnic_no')
    def _check_cnic_format(self):
        for record in self:
            if record.cnic_no:
                if not re.match(cnic_pattern, record.cnic_no):
                    raise ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.cnic_no.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")

    @api.onchange('cnic_no')
    def _onchange_cnic_no(self):
        if self.cnic_no and self.search_type == 'cnic_no':
            cleaned_cnic = re.sub(r'[^0-9]', '', self.cnic_no)
            if len(cleaned_cnic) >= 13:
                self.cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:12]}-{cleaned_cnic[12:]}"
            elif len(cleaned_cnic) > 5:
                self.cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:]}"

    def action_search(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Confirmation',
            'res_model': 'confirm.search',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_profile_management.confirm_search_view_form').id,
            'context': {
                'default_search_type': self.search_type,
                'default_registration_id': self.registration_id,
                'default_country_code_id': self.country_code_id.id,
                'default_mobile_no': self.mobile_no,
                'default_cnic_no': self.cnic_no,
                'default_registration_type': self.registration_type,
                'default_donee_registration_type': self.donee_registration_type,
                # 'default_scheme_type_id': self.scheme_type_id.id,
            },
            'target': 'new',
        }