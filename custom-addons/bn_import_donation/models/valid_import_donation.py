from odoo import models, fields


class ValidImportDonation(models.Model):
    _name = 'valid.import.donation'
    _description = "Valid Import Donation"


    import_donation_id = fields.Many2one('import.donation', string="Import Donation")

    transaction_id = fields.Char('Transacetion ID')
    donor_student_name = fields.Char('Donor / Student Name')
    mobile = fields.Char('Mobile No.', size=10)
    cnic_no = fields.Char('CNIC No.')
    email = fields.Char('Email')
    product = fields.Char('Product')
    date = fields.Char('Date')
    amount = fields.Float('Amount')
    reference = fields.Char('Reference')

    is_student = fields.Boolean('Is Student', default=False)