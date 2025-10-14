from email.policy import default

from odoo import api, fields, models, _
from odoo.exceptions import UserError


category_selection = [
    ('institute','Institute'),
    ('individual','Individual'),
    ('rider', 'Rider'),
    ('walk_in_donee', 'Walk-In Donee'),
    ('walk_in_donor', 'Walk-In Donor'),
    ('premium_individual_donor', 'Premium Individual Donor'),
    ('premium_corporate_donor', 'Premium Corporate Donor'),
    ('donation_box', 'Donation Box'),
    ('online', 'Online'),
    ('student', 'Student'),
    ('microfinance_loans', 'Microfinance Loans'),
    ('employees', 'Employees'),
    ('medical_patients', 'Medical Patients'),
    ('medical_equipment', 'Medical Equipment'),
    ('donors_of_associated_companies', 'Donors Of Associated Companies'),
    ('donation_by_home', 'Donation By Home Service'),
]

donation_type_selection = [
    ('cash', 'Cash'),
    ('cheque',  'Cheque'),
    ('in_kind', 'In-Kind'),
]

class ResPartnerModel(models.Model):
    _inherit = 'res.partner'

    serial_number = fields.Char(string='Serial Number')
    reference_number = fields.Char(string='Remark')
    cnic_no = fields.Char(string='CNIC')
    category = fields.Selection(selection=category_selection, string='Category', default='walk_in_donor')
    donation_type =  fields.Selection(selection=donation_type_selection, string='Donation Type')
    amount = fields.Integer(string='Amount')
    bank_name = fields.Char(string="Bank Name")
    cheque_number = fields.Integer(string="Cheque Number")
    branch_id = fields.Many2one(comodel_name='res.company', string="Branch")
    delivery_charges_amount = fields.Integer(string='Delivery Charges Amount')
    donation_service = fields.Many2one(comodel_name='donation.by.home.service', string="Donation By Home Service")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'category' not in vals or not vals['category']:
                raise UserError("Category cannot be empty when creating a record.")
            vals['serial_number'] = self.env['ir.sequence'].next_by_code(vals['category'])
        result = super(ResPartnerModel, self).create(vals_list)
        return result

    def write(self, vals):
        if 'category' in vals and not vals['category']:
            raise UserError("Category cannot be empty when updating a record.")
        result = super(ResPartnerModel, self).write(vals)
        return result

