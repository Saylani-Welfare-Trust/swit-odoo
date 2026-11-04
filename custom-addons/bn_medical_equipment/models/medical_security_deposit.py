from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import re
_logger = logging.getLogger(__name__)

payment_method_selection = [
    ('cash', 'Cash'),
    ('cheque', 'Cheque'),
]

state_selection = [
    ('draft', 'Draft'),
    ('pending', 'Pending'),
    ('paid', 'Paid'),
    ('bounced', 'Bounced')
]


class MedicalSecurityDeposit(models.Model):
    _name = 'medical.security.deposit'
    _description = "Medical Security Deposit"


    name = fields.Char('Name', default="NEW")
    cnic_no = fields.Char('CNIC No.', size=15)
    bank_name = fields.Char('Bank Name')
    cheque_no = fields.Char('Cheque No.')

    payment_method = fields.Selection(selection=payment_method_selection, string="Payment Method")
    state = fields.Selection(selection=state_selection, string='Status', default='draft')

    donee_id = fields.Many2one('res.partner', string="Donee")
    medical_equipment_id = fields.Many2one('medical.equipment', string="Medical Equipment")
    currency_id = fields.Many2one('res.currency', related='medical_equipment_id.currency_id')

    amount = fields.Monetary('Amount', currency_field='currency_id')

    date = fields.Date('Date')
    cheque_date = fields.Date('Cheque Date')


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'NEW') == 'NEW':
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('installment_slip') or 'New'
        return super().create(vals_list)
    
    @api.constrains('cnic_no')
    def _check_cnic_format(self):
        for record in self:
            if record.cnic_no:
                if not re.match(r'^\d{5}-\d{7}-\d{1}$', record.cnic_no):
                    raise ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.cnic_no.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")

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

            if not self.is_valid_cnic_format(self.cnic_no):
                raise ValidationError('Invalid CNIC No. format ( acceptable format XXXXX-XXXXXXX-X )')
    
    @api.model
    def get_medical_equipment_security_deposit(self, data):
        """POS 'me' provisional popup: the security deposit to collect for a
        request. The deposit itself is recorded when the order is saved
        (pos.order._apply_medical_equipment_payment)."""
        medical_equipment_request = self.env['medical.equipment'].search(
            [('name', '=', data['medical_equipment_request_no'])],
            limit=1
        )

        if not medical_equipment_request:
            return {
                'status': "error",
                'body': _("No request found against entered number."),
            }

        security_deposit = medical_equipment_request._get_security_deposit()
        if security_deposit.state == 'paid':
            return {'status': "error", 'body': _("The security deposit of %s is already paid.") % medical_equipment_request.name}
        if security_deposit.state == 'pending':
            return {'status': "error", 'body': _("The security deposit of %s waits for its cheque to clear.") % medical_equipment_request.name}

        donee = medical_equipment_request.donee_id
        return {
            'status': "success",
            'id': medical_equipment_request.id,
            'donee_id': donee.id,
            'donee_name': donee.name or '',
            'cnic_no': donee.cnic_no or '',
            'deposit_id': security_deposit.id,
            # a draft / bounced deposit is collected again
            'deposit_exists': False,
            # one line for the whole deposit of the request
            'amount': medical_equipment_request.total_amount,
            'quantity': 1,
            'date': fields.Date.today(),
        }