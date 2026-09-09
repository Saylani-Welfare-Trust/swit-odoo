from odoo import models, fields, api
from odoo.exceptions import ValidationError

import re


class InvalidImportDonation(models.Model):
    _name = 'invalid.import.donation'
    _description = "Invalid Import Donation"


    import_donation_id = fields.Many2one('import.donation', string="Import Donation")

    transaction_id = fields.Char('Transacetion ID')
    donor_student_name = fields.Char('Donor / Student Name')
    mobile = fields.Char('Mobile No.', size=10)
    cnic_no = fields.Char('CNIC No.', size=15)
    email = fields.Char('Email')
    product = fields.Char('Product')
    date = fields.Char('Date')
    amount = fields.Float('Amount')
    reference = fields.Char('Reference')

    reason = fields.Char('Reason')
    is_student = fields.Boolean('Is Student', default=False)
    create_record = fields.Boolean('Create Contact', default=False)
    hide_button = fields.Boolean('Hide Button', default=False)


    @api.constrains('mobile')
    def _check_mobile_number(self):
        for rec in self:
            if rec.mobile:
                if not re.fullmatch(r"\d{10}", rec.mobile):
                    raise ValidationError(
                        "Mobile number must contain exactly 10 digits."
                    )

    def action_approve(self):
        donation_id = self.env['donation'].search([('transaction_id', '=', self.transaction_id)])

        if donation_id:
            self.reason = 'A Transaction with same ID already exist in the System.'
            self.hide_button = True
            return True

        partner_obj = None

        if self.create_record:
            partner_obj = self.env['res.partner'].create({
                'name': self.donor_name,
                'mobile': self.mobile,
                'cnic_no': self.cnic_no,
                'email': self.email,
                'cateegory_id': [(6, 0, [self.env.ref('bn_profile_management.donor_partner_category').id, self.env.ref('bn_profile_management.individual_partner_category').id])]
            })

            partner_obj.action_register()

        transaction_id = self.transaction_id
        mobile_no = self.mobile
        product = self.product
        fund_utilization = self.analytic_account_id
        date = self.date
        amount = self.amount
        reference = self.reference
    
        partner_id = self.env['res.partner'].search([('mobile', '=', mobile_no)], limit=1)

        if not partner_id:
            self.reason = f'A Donor against specified mobile no. ( {mobile_no} ) does not exist in the System.'
            self.create_record = True
            return True

        if not fund_utilization:
            raise ValidationError(str(f'The specified ( {fund_utilization.name} ) Fund Utilization does not match our SOP.'))
        
        product_id = self.import_donation_id.gateway_config_id.gateway_config_line_ids.filtered(lambda x: x.name == product).mapped('product_id')[0]
        if not product_id:
            raise ValidationError(str(f'The specified ( {product} ) Product does not exist in the System'))

        credit_account = self.import_donation_id.gateway_config_id.gateway_config_line_ids.filtered(lambda x: x.name == product).mapped('account_id.id')[0]
        if not credit_account:
            raise ValidationError(str(f'The specified ( {credit_account} ) Credit Account does not exist in the System or is not configure.'))
        

        self.env['valid.import.donation'].create({
            'import_donation_id': self.import_donation_id.id,
            'transaction_id': transaction_id,
            'donor_name': self.donor_name,
            'mobile': self.mobile,
            'cnic_no': self.cnic_no,
            'email': self.email,
            'product': self.product,
            'fund_utilization': self.analytic_account_id.id,
            'date': self.date,
            'amount': self.amount,
            'reference': self.reference,
        })

        self.hide_button = True