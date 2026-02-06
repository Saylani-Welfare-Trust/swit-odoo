from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import re


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


    @api.model
    def create(self, vals):
        if vals.get('name', _('NEW') == _('NEW')):
            vals['name'] = self.env['ir.sequence'].next_by_code('installment_slip') or ('New')
                
        return super(MedicalSecurityDeposit, self).create(vals)
    
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
    def set_security_depsoit_values(self, data):
        security_deposit = self.search(
            [('id', '=', data.get('deposit_id')), ('state', 'in', ['draft', 'pending'])],
            limit=1
        )

        if security_deposit:
            security_deposit.payment_method = data.get('payment_method')
            security_deposit.bank_name = data.get('bank_name')
            security_deposit.cheque_no = data.get('cheque_no')
            security_deposit.cheque_date = data.get('cheque_date')
            security_deposit.state = data.get('state')

            security_deposit.medical_equipment_id.sd_slip_id = security_deposit.id
            security_deposit.medical_equipment_id.state = 'sd_received'

    @api.model
    def get_medical_equipment_security_deposit(self, data):

        medical_equipment_request = self.env['medical.equipment'].search(
            [('name', '=', data['medical_equipment_request_no'])],
            limit=1
        )

        if not medical_equipment_request:
            return {
                'status': "error",
                'body': "No request found against entered number."
            }

        security_deposit = self.search(
            [('medical_equipment_id', '=', medical_equipment_request.id)],
            limit=1
        )

        if security_deposit:
            return {
                'status': "success",
                'id': medical_equipment_request.id,
                'donee_id': medical_equipment_request.donee_id.id,
                'deposit_id': security_deposit.id,
                'amount': security_deposit.amount,
                'state': security_deposit.state,
                'deposit_exists': True
            }

        # ✅ calculate amount properly
        amount = sum(
            line.medical_equipment_category_id.security_deposit
            for line in medical_equipment_request.medical_equipment_line_ids
        )
        quantity = sum(
            line.quantity
            for line in medical_equipment_request.medical_equipment_line_ids
        )

        # ✅ create with ALL values
        deposit = self.create({
            'medical_equipment_id': medical_equipment_request.id,
            'donee_id': medical_equipment_request.donee_id.id,
            'amount': amount,
        })

        return {
            'status': "success",
            'id': medical_equipment_request.id,
            'donee_id': medical_equipment_request.donee_id.id,
            'deposit_id': deposit.id,
            'amount': amount,
            'quantity': quantity,
            'deposit_exists': False
        }