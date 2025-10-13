from odoo import fields, api, models,_
from odoo.exceptions import UserError, ValidationError
import re


class AdvanceDonation(models.Model):
    _name = 'adv.don.customer'

    sequence = fields.Char(string="Name", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    name = fields.Char(string='Name')
    email = fields.Char(string='Email')
    address = fields.Char(string='Address')
    phone_no = fields.Char(string='Phone No')
    cnic = fields.Char(string='CNIC', size=15)

    @api.constrains('cnic')
    def _check_cnic_format(self):
        for record in self:
            if record.cnic:
                if not re.match(r'^\d{5}-\d{7}-\d{1}$', record.cnic):
                    raise ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.cnic.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")

    @api.onchange('cnic')
    def _onchange_cnic(self):
        if self.cnic:
            cleaned_cnic = re.sub(r'[^0-9]', '', self.cnic)
            if len(cleaned_cnic) >= 13:
                self.cnic = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:12]}-{cleaned_cnic[12:]}"
            elif len(cleaned_cnic) > 5:
                self.cnic = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:]}"

    @api.model
    def create(self, vals):
        if vals.get('sequence', _('New') == _('New')):
            vals['sequence'] = self.env['ir.sequence'].next_by_code('advance.donation.customer') or ('New')
        return super().create(vals)
