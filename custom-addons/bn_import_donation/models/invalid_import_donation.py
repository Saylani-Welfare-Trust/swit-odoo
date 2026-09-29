from odoo import models, fields, api, _
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
        self.ensure_one()

        existing = self.env['donation'].search([('transaction_id', '=', self.transaction_id)], limit=1)
        if existing:
            self.reason = 'A Transaction with same ID already exist in the System.'
            self.hide_button = True
            return True

        partner_id = self.env['res.partner'].search([('mobile', '=', self.mobile)], limit=1)

        if not partner_id:
            if self.create_record:
                donor_category = self.env.ref('bn_profile_management.donor_partner_category', raise_if_not_found=False)
                individual_category = self.env.ref('bn_profile_management.individual_partner_category', raise_if_not_found=False)
                partner_id = self.env['res.partner'].create({
                    'name': self.donor_student_name,
                    'mobile': self.mobile,
                    'cnic_no': self.cnic_no,
                    'email': self.email,
                    'category_id': [(6, 0, [c.id for c in (donor_category, individual_category) if c])],
                })
                partner_id.action_register()
            else:
                self.reason = f'A Donor against specified mobile no. ( {self.mobile} ) does not exist in the System.'
                self.create_record = True
                return True

        gateway_lines = self.import_donation_id.gateway_config_id.gateway_config_line_ids.filtered(
            lambda x: x.name == self.product)

        product = gateway_lines.mapped('product_id')[:1]
        if not product:
            raise ValidationError(_('The specified ( %s ) Product does not exist in the System.') % self.product)

        credit_account = gateway_lines.mapped('account_id')[:1]
        if not credit_account:
            raise ValidationError(_(
                'The specified ( %s ) Credit Account does not exist in the System or is not configured.'
            ) % self.product)

        self.env['valid.import.donation'].create({
            'import_donation_id': self.import_donation_id.id,
            'transaction_id': self.transaction_id,
            'donor_student_name': self.donor_student_name,
            'mobile': self.mobile,
            'cnic_no': self.cnic_no,
            'email': self.email,
            'product': self.product,
            'date': self.date,
            'amount': self.amount,
            'reference': self.reference,
            'is_student': self.is_student,
        })

        self.hide_button = True