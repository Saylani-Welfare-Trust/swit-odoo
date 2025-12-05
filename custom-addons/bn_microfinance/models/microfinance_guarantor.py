from odoo import models, fields, api
from odoo.exceptions import ValidationError

import re


class MicrofinanceGuarantor(models.Model):
    _name = 'microfinance.guarantor'
    _description = "Microfinance Guarantor"


    microfinance_id = fields.Many2one('microfinance', string="Microfinance")

    name = fields.Char('Name')
    father_spouse_name = fields.Char('Father / Spouse Name')
    landline_no = fields.Char('Landline No.')
    address = fields.Char('Address')
    cnic_no = fields.Char('CNIC No.', size=13)
    mobile = fields.Char('Mobile No.', size=10)
    phone_code_id = fields.Many2one('res.country', string="Phone Code")

    relation = fields.Char('Relation')
    occupation = fields.Char('Occupation')

    @api.constrains('cnic_no')
    def _check_cnic_format(self):
        for record in self:
            if record.cnic_no:
                if not re.match(r'^\d{5}-\d{7}-\d{1}$', record.cnic_no):
                    raise ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.cnic_no.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")

    def is_valid_cnic_characters(cnic):
        """Return True only if CNIC contains digits and '-' only."""
        return bool(re.fullmatch(r'[0-9-]*', cnic))

    @api.onchange('cnic_no')
    def _onchange_cnic_no(self):
        if self.cnic_no:
            cleaned_cnic = re.sub(r'[^0-9]', '', self.cnic_no)
            if len(cleaned_cnic) >= 13:
                self.cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:12]}-{cleaned_cnic[12:]}"
            elif len(cleaned_cnic) > 5:
                self.cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:]}"
            
            if not self.is_valid_cnic_characters(self.cnic_no):
                raise ValidationError('Invalid CNIC No. Can contain only digit and -')