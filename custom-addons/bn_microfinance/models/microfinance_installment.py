from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import re


payment_type_selection = [
    ('security', 'Security Deposite'),
    ('installment', 'Installment Deposite'),
]

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


class MicrofinanceInstallment(models.Model):
    _name = 'microfinance.installment'
    _description = "Microfinance Installment"


    name = fields.Char('Name', default="NEW")
    cnic_no = fields.Char('CNIC No.', size=15)
    bank_name = fields.Char('Bank Name')
    cheque_no = fields.Char('Cheque No.')

    payment_type = fields.Selection(selection=payment_type_selection, string="Payment Type")
    payment_method = fields.Selection(selection=payment_method_selection, string="Payment Method")
    state = fields.Selection(selection=state_selection, string='Status', default='draft')

    donee_id = fields.Many2one('res.partner', string="Donee")
    microfinance_id = fields.Many2one('microfinance', string="Microfinance")
    currency_id = fields.Many2one('res.currency', related='microfinance_id.currency_id')

    amount = fields.Monetary('Amount', currency_field='currency_id')

    date = fields.Date('Date')
    cheque_date = fields.Date('Cheque Date')


    @api.model
    def create(self, vals):
        if vals.get('name', _('NEW') == _('NEW')):
            payment_type = vals.get('payment_type')
            
            if payment_type == 'security':
                vals['name'] = self.env['ir.sequence'].next_by_code('sd_slip') or ('New')
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('installment_slip') or ('New')
                
        return super(MicrofinanceInstallment, self).create(vals)
    
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
    def create_microfinance_security_deposit(self, data):
        microfinance_request = self.env['microfinance'].search([('name', '=', data['microfinance_request_no'])])

        if not microfinance_request:
            return {
                'status': "error",
                'body': "No request found against enter number."
            }
        
        if data['amount'] and data['amount'] < 1:
            return {
                'status': "error",
                'body': "Amount can't be zero or negative."
            }
        elif data['amount'] != microfinance_request.security_deposit:
            return {
                'status': "error",
                'body': "Please enter the correct security deposit amount."
            }


        if self.search([('microfinance_id', '=', microfinance_request.id)]):
            return {
                'status': "error",
                'body': "Someone has already paid the Security Deposit against this request."
            }

        microfinance_installment = self.create({
            'payment_type': 'security',
            'amount': data['amount'],
            'microfinance_id': microfinance_request.id,
            'donee_id': microfinance_request.donee_id.id,
            'date': fields.Date.today()
        })

        if microfinance_installment:
            return {
                'status': "success",
                'id': microfinance_request.id,
                'donee_id': microfinance_request.donee_id.id,
                'deposit_id': microfinance_installment.id
            }
    
    @api.model
    def get_microfinance_security_deposit(self, data):
        microfinance_request = self.env['microfinance'].search([('name', '=', data['microfinance_request_no'])])

        if not microfinance_request:
            return {
                'status': "error",
                'body': "No request found against enter number."
            }

        security_deposit = self.search([('microfinance_id', '=', microfinance_request.id), ('payment_type', '=', 'security')])
        
        if security_deposit:
            return {
                'status': "success",
                'id': microfinance_request.id,
                'donee_id': microfinance_request.donee_id.id,
                'deposit_id': security_deposit.id,
                'amount': security_deposit.amount,
                'deposit_exists': True
            }
        
        # Return microfinance info even if no deposit exists, so POS can create it
        return {
            'status': "success",
            'id': microfinance_request.id,
            'donee_id': microfinance_request.donee_id.id,
            'deposit_id': False,
            'amount': microfinance_request.security_deposit,
            'deposit_exists': False
        }