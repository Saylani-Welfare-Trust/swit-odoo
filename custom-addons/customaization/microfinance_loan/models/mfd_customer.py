from odoo import fields, api, models, _
from datetime import datetime

class MfdCustomer(models.Model):
    _inherit = 'res.partner'

    is_mfd_customer = fields.Boolean()
    sequence = fields.Char(string="Id", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    customer_image = fields.Image()


    name = fields.Char(string='Name')
    father_name = fields.Char(string='Father Name')
    dob = fields.Date(string='Date of Birth')
    user_gender = fields.Selection([('male', 'Male'),
                                    ('female', 'Female')],
                                   string='Gender', default=False)
    phone_no = fields.Char(string='Phone No')
    martial_status = fields.Selection([('married', 'Married'),
                                      ('unmarried', 'UnMarried')],
                                     string='Marital Status', default='married')

    address = fields.Char(string='Address')
    cnic = fields.Char(string='CNIC')
    domicile = fields.Char(string='Domicile')
    driving_license = fields.Selection([('no', 'No'),
                                      ('yes', 'Yes')],
                                     string='Having Driving Liscense', default='no')

    is_employee = fields.Boolean(string="Is Employee?")
    employee_id = fields.Many2one('hr.employee', string="Employee")

    # Form 1
    # Home Information
    rental_duration = fields.Char(string='Rental Duration')
    house_electricity_bill = fields.Float(string='Electricity Bill Amount of 6 months')
    dependent_person = fields.Integer(string='Dependent number of Person')
    monthly_expenses = fields.Float(string='Monthly Expenses')
    monthly_income = fields.Float(string='Monthly Income')
    # Any Other Person Income Details
    other_person_name = fields.Char(string='Name')
    other_person_occupation = fields.Char(string='Occupation')
    other_person_income = fields.Float(string='Income')
    # Owner's Information
    owner_name = fields.Char(string='Name')
    onwer_cnic = fields.Char(string='CNIC')
    onwer_phone = fields.Char(string='Phone No')
    other_owner_info = fields.Html(string='Others')
    # Office Information
    office_id = fields.Char(string='Id')
    office_name = fields.Char(string='Organization Name')
    office_designation = fields.Char(string='Designation')
    office_supervisor = fields.Char(string='Supervisor')
    shift_type = fields.Selection([('half', 'Half'),
                                        ('full', 'Full')],
                                       string='Shift', default='full')
    office_monthly_income = fields.Float(string='Monthly Income')
    office_total_income = fields.Float(string='Total Income')
    # Other Home Income Information
    other_home_information = fields.Html(string='Details')
    # Any Other Personal Problem
    other_personal_problem = fields.Html(string='Details')
    #Attachment
    attachment_id = fields.Binary(string="Attach Form")
    attachment_name = fields.Char()

    # Guarantor Information

    # Person 1
    person1_name = fields.Char(string='Name')
    person1_cnic = fields.Char(string='CNIC')
    person1_address = fields.Char(string='Address')
    person1_phone = fields.Char(string='Phone No')
    person1_occupation = fields.Char(string='Occupation')
    person1_relation = fields.Char(string='Relation')
    # Person 2
    person2_name = fields.Char(string='Name')
    person2_cnic = fields.Char(string='CNIC')
    person2_address = fields.Char(string='Address')
    person2_phone = fields.Char(string='Phone No')
    person2_occupation = fields.Char(string='Occupation')
    person2_relation = fields.Char(string='Relation')
    # Person 3
    person3_name = fields.Char(string='Name')
    person3_cnic = fields.Char(string='CNIC')
    person3_address = fields.Char(string='Address')
    person3_phone = fields.Char(string='Phone No')
    person3_occupation = fields.Char(string='Occupation')
    person3_relation = fields.Char(string='Relation')


    # For Office Use
    application_date = fields.Date(string='Application Date')
    application_no = fields.Char(string='Application Number')
    receiver_name = fields.Char(string='Receiver Name')
    interview = fields.Selection([('no', 'No'),
                                        ('yes', 'Yes')],
                                       string='Interview', default='yes')
    interview_date = fields.Date(string='Interview Date')
    # advance_deposit = fields.Float(string='Advance Deposit')
    # monthly_deposit = fields.Float(string='Monthly Deposit')
    duration = fields.Char(string='Duration')
    having_account = fields.Selection([('no', 'No'),
                                  ('yes', 'Yes')],
                                 string='Having Bank Account', default='yes')

    # Form 2
    # cast = fields.Char(string='Cast')
    # ntn_no = fields.Char(string='NTN No')


    @api.model
    def create(self, vals):
        dob = vals.get('dob')
        user_gender = vals.get('user_gender')

        current_year_last_two_digits = datetime.now().year % 100
        dob_year_last_two_digits = datetime.strptime(dob, '%Y-%m-%d').year % 100

        sequence = f"{current_year_last_two_digits:02d}{dob_year_last_two_digits:02d}-"

        if vals.get('name', _('New') == _('New')):
            sequence += self.env['ir.sequence'].next_by_code('mfd.customer') or ('New')
        if user_gender == 'male':
            sequence += "-01"
        else:
            sequence += "-02"

        vals['sequence'] = sequence
        return super().create(vals)
