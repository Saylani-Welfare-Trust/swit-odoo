from odoo import models, fields, api
from odoo.exceptions import ValidationError

import re

# CNIC regular expression
cnic_pattern = r'^\d{5}-\d{7}-\d{1}$'


class HREmployee(models.Model):
    _inherit = 'hr.employee'


    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", tracking=True)

    # HR only: a national ID is personal data (not on the public directory).
    cnic_no = fields.Char('CNIC No.', size=15, tracking=True, groups='hr.group_hr_user')


    @api.constrains('cnic_no')
    def _check_cnic_no_format(self):
        for record in self:
            if record.cnic_no:
                if not re.match(cnic_pattern, record.cnic_no):
                    raise ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.cnic_no.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")

    @api.constrains('cnic_no')
    def _check_cnic_no_unique(self):
        for record in self.filtered('cnic_no'):
            if self.search_count([('cnic_no', '=', record.cnic_no), ('id', '!=', record.id)]):
                raise ValidationError("An employee with the same CNIC No. already exists.")

    def is_valid_cnic_format(self, cnic):
        return bool(re.fullmatch(r'\d{5}-\d{7}-\d', cnic))

    @api.onchange('cnic_no')
    def _onchange_cnic_no(self):
        if self.cnic_no:
            cleaned_cnic = re.sub(r'[^0-9]', '', self.cnic_no)
            if len(cleaned_cnic) >= 13:
                self.cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:12]}-{cleaned_cnic[12:]}"
            elif len(cleaned_cnic) > 5:
                self.cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:]}"

            if self.search([('cnic_no', '=', self.cnic_no), ('id', '!=', self._origin.id)]):
                raise ValidationError("A User with same CNIC No. already exist.")

            if not self.is_valid_cnic_format(self.cnic_no):
                raise ValidationError('Invalid CNIC No. format ( acceptable format XXXXX-XXXXXXX-X )')
            
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            barcode = vals.get('barcode')
            if barcode and vals.get('name'):
                vals['name'] = "%s ( %s )" % (vals['name'], barcode)

        return super().create(vals_list)