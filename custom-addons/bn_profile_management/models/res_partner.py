from odoo import fields, models, api, _, exceptions
import random
import string
from odoo.exceptions import UserError, ValidationError
import re

# CNIC regular expression
cnic_pattern = r'^\d{5}-\d{7}-\d{1}$'
# Email regular expression
#email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
#email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$'
# BY IH: matches any string (even empty)
#email_pattern = r'^.*$'
# Regular expression for NTN validation (7 or 8 digits)
ntn_pattern = r'^\d{7}$|^\d{8}$|^\d{13}$'


donee_selection = [
    ('individual', 'Individual'),
    ('institute', 'Institute'),
]

donor_selection = [
    ('individual', 'Individual'),
    ('coorporate', 'Corporate'),
]

gender_selection = [
    ('male', 'Male'),
    ('female', 'Female'),
]

state_selection = [
    ('draft', 'Draft'),
    ('validate', 'Validate'),
    ('print_info', 'Print Info'),
    ('reject', 'Rejected'),
    ('register', 'Registered'),
    ('change_request', 'Change Request'),
]

martial_selection = [
    ('unmarried', 'Unmarried'),
    ('married', 'Married'),
    ('divorce', 'Divorce'),
]

general_selection = [
    ('no', 'No'),
    ('yes', 'Yes'),
]

job_selection = [
    ('part_time', 'Part Time'),
    ('full_time', 'Full Time'),
]

donation_type_selection = [
    ('cash', 'Cash'),
    ('cheque',  'Cheque'),
    ('in_kind', 'In-Kind'),
]

registration_category_selection = [
    ('donee', 'Donee'),
    ('donor',  'Donor'),
    ('vendor', 'Vendor'),
    ('customer', 'Customer'),
]

# microfinance_application_selection = [
#     ('asan_qarz', 'Asan Qarz'),
#     ('asan_karobar',  'Asan Karobar'),
#     ('rickshaw', 'Rickshaw'),
#     ('motor_cycle', 'Motor Cycle'),
#     ('housing', 'Housing'),
#     ('laptop', 'Laptop'),
#     ('mobile', 'Mobile'),
# ]

# welfare_application_selection = [
#     ('madad_kifalat', 'Madad / Kifalat'),
# ]

religion_selection = [
    ('muslim', 'Muslim'),
    ('non_muslim', 'Non Muslim'),
    ('syed', 'Syed'),
]

residence_selection = [
    ('owned', 'Owned'),
    ('shared', 'Shared'),
    ('rented', 'Rented'),
]

loan_tenure_selection = [
    ('12M', '12 Months'),
    ('24M', '24 Months'),
    ('36M', '36 Months'),
    ('other', 'Other'),
]

kifalat_madad_tenure_selection = [
    ('one_time', 'One Time'),
    ('3M', '3 Months'),
    ('6M', '6 Months'),
    ('1Y', '1 Year'),
    ('3Y', '3 Year'),
    ('other', 'Other'),
]

class ResPartner(models.Model):
    _inherit = 'res.partner'


    application_number = fields.Char('Application Number', readonly=True)

    gender = fields.Selection(selection=gender_selection, string="Gender", tracking=True)
    donee_type = fields.Selection(selection=donee_selection, string="Donee Type", tracking=True)
    donor_type = fields.Selection(selection=donor_selection, string="Donor Type", tracking=True)
    cnic = fields.Selection(selection=general_selection, string="CNIC", default="yes", tracking=True)
    state = fields.Selection(selection=state_selection, string="Status", default="draft", tracking=True)
    donation_type =  fields.Selection(selection=donation_type_selection, string='Donation Type', tracking=True)
    martial_status = fields.Selection(selection=martial_selection, string="Martial Status", default='unmarried', tracking=True)
    religion_category = fields.Selection(selection=religion_selection, string="Religion", default="muslim", tracking=True)
    registration_category = fields.Selection(selection=registration_category_selection, string="Registration Catgeory", tracking=True)
    phone = fields.Char(unaccent=False, size=11)
    mobile = fields.Char(unaccent=False, size=10)
    phone_code_id = fields.Many2one('res.country', string="Phone Code")

    # welfare_application_type = fields.Selection(selection=welfare_application_selection, string="Application Type", tracking=True)
    # microfinance_application_type = fields.Selection(selection=microfinance_application_selection, string="Application Type", tracking=True)

    cnic_no = fields.Char('CNIC No.', tracking=True)
    next_kin = fields.Char('Next kin', tracking=True)
    surname_name = fields.Char('Surname', tracking=True)
    father_name = fields.Char('Father Name', tracking=True)
    spouse_name = fields.Char('Spouse Name', tracking=True)
    head_cnic_no = fields.Char('Head CNIC No.', size=15, tracking=True)
    member_cnic_no = fields.Char('Member CNIC No.', size=15, tracking=True)
    father_cnic_no = fields.Char('Father CNIC No.', size=15, tracking=True)
    nearest_land_mark = fields.Char('Nearest Land Mark', tracking=True)
    bank_wallet_account = fields.Char('Bank / Wallet Account', tracking=True)
    old_system_record = fields.Char('Old System Record')

    cnic_back = fields.Binary('CNIC Back')
    cnic_front = fields.Binary('CNIC Front')
    reference_letter = fields.Binary('Reference Letter')
    approved_form = fields.Binary('Approved Form')

    detail = fields.Text('Details', tracking=True)
    reference_remarks = fields.Text('Reference / Remarks', tracking=True)

    date_of_birth = fields.Date('Date of Birth', tracking=True)

    age = fields.Integer('Age',compute="_compute_age", store=True)
    
    donee_id = fields.Many2one('res.partner', string="Donee ID", tracking=True)
    donee_registration_id = fields.Char(related='donee_id.barcode', string="Donee Registration ID", tracking=True)
    donor_id = fields.Many2one('res.partner', string="Donor ID", tracking=True)
    donor_registration_id = fields.Char(related='donor_id.barcode', string="Donor Registration ID", tracking=True)
    branch_id = fields.Many2one('res.company', string="Branch ID", default=lambda self: self.env.company.id, tracking=True)
    employee_id = fields.Many2one('hr.employee', string="Employee ID", tracking=True)

    course_ids = fields.Many2many('product.product', string="Course IDs", tracking=True)

    is_donee = fields.Boolean('Is Donee', tracking=True)
    is_rider = fields.Boolean('Is Rider', tracking=True)
    is_medical = fields.Boolean('Is Medical', tracking=True)
    is_welfare = fields.Boolean('Is Welfare', tracking=True)
    is_student = fields.Boolean('Is Student', tracking=True)
    is_employee = fields.Boolean('Is Employee', tracking=True)
    is_microfinance = fields.Boolean('Is MicroFinance', tracking=True)
    is_donation_box = fields.Boolean('Is Donation Box', tracking=True)
    is_change_request = fields.Boolean('Is Change Request', tracking=True)
    is_donation_by_home = fields.Boolean('Is Donation by Home', tracking=True)

    # Student
    student_qualification_ids = fields.One2many('student.qualification', 'partner_id', string="Student Qualification IDs")

    # For institution
    reg_no = fields.Char('Registration No', tracking=True)
    contact_person_name = fields.Char('Contact Person Name', tracking=True)
    authorized_person_name = fields.Char('Authorized Person Name', tracking=True)
    authorized_person_cell = fields.Char('Authorized Person Cell', tracking=True)
    authorized_person_cnic = fields.Char('Authorized Person CNIC', size=15, tracking=True)
    institution_referred_by = fields.Char('Institution Referred By', tracking=True)
    
    date_of_incorporation = fields.Date('Date of Incorporation', tracking=True)

    reference = fields.Text('Reference', tracking=True)

    # Welfare
    welfare_qualification_ids = fields.One2many('welfare.qualification', 'partner_id', string="Welfare Qualification IDs")
    
    # For MicroFinance
    guarantor_information_ids = fields.One2many('guarantor.information', 'partner_id', string='Guarator Information IDs')
    microfinance_qualification_ids = fields.One2many('microfinance.qualification', 'partner_id', string="MicroFinance Qualification IDs")
    
    # House Ownership / Residency Details
    residence_type = fields.Selection(selection=residence_selection, string="Residence Type", tracking=True)

    home_phone_no = fields.Char('Home Phone No.', tracking=True)
    cnic_no_landlord = fields.Char('CNIC No. of Landlord', tracking=True)
    mobile_no_landlord = fields.Char('Mobile No. of Landlord', tracking=True)
    landlord_owner = fields.Char('Name of Landlord / Owner', tracking=True)
    rental_shared_duration = fields.Char('Rental / Shared Duration', tracking=True)
    
    per_month_rent = fields.Float('Per month Rent', tracking=True)
    gas_bill = fields.Float('Cumulative Gas Bill of 6 Months (Total)', tracking=True)
    electricity_bill = fields.Float('Cumulative Electricity Bill of 6 Months (total)', tracking=True)
    
    home_other_info = fields.Text('Other info / Addres of Landlord', tracking=True)

    # Family Members' Detail
    dependent_person = fields.Integer('Number of Dependents', tracking=True)
    household_member = fields.Integer('Household members', tracking=True)
    family_information_ids = fields.One2many('family.information', 'partner_id', string='Guarator Information IDs')

    # Request Details
    loan_request_amount = fields.Float('Loan Request Amount', tracking=True)
    
    loan_tenure_expected = fields.Selection(selection=loan_tenure_selection, string='Loan Tenure Expected', tracking=True)
    tenure_kifalat_madad_expected = fields.Selection(selection=kifalat_madad_tenure_selection, string='Tenure of Kifalat / Madad expected', tracking=True)

    security_offered = fields.Char('Security Offered', tracking=True)

    # Other Information
    aid_from_other_organization = fields.Selection(selection=general_selection, string="Aid from Other Organisation", tracking=True)
    have_applied_swit = fields.Selection(selection=general_selection, string="Have you ever applied with SWIT?", tracking=True)

    details_1 = fields.Text('Details 1', tracking=True)
    details_2 = fields.Text('Details 2', tracking=True)
    
    driving_license = fields.Selection(selection=general_selection, string="Driving License", tracking=True)

    # Other Financial Information
    monthly_income = fields.Float('Monthly Income', tracking=True)
    outstanding_amount = fields.Float('Outstanding Amount', tracking=True)
    monthly_household_expense = fields.Float('Monthly Household Expenses', tracking=True)
    
    bank_account = fields.Selection(selection=general_selection, string="Bank Account", tracking=True)
    
    bank_name = fields.Char('Bank Name', tracking=True)
    account_no = fields.Char('Account No', tracking=True)
    institute_name = fields.Char('Institution Name', tracking=True)

    other_loan = fields.Selection(selection=general_selection, string="Any Other Loan?", tracking=True)

    # Employment Details
    company_name = fields.Char('Company Name', tracking=True)
    company_address = fields.Char('Company Address', tracking=True)
    company_phone_no = fields.Char('Company Phone No.', tracking=True)
    designation = fields.Char('Designation', tracking=True)
    duration_of_service = fields.Char('Duration of service (in years)', tracking=True)

    monthly_salary = fields.Float('Monthly Salary', tracking=True)


    # Mudasir
    disbursement_type = fields.Selection([('in_kind','In Kind Support'),('cash','Cash Support')],string='Disbursement Type')
    in_kind_transaction_type = fields.Selection([
        ('ration','Ration Support'),
        ('ramzan','Ramzan Support'),
        ('meal','Meal Distribution'),
        ('medicines','Medicines - General'),
        ('medicines_cancer','Medicines - Cancer Support'),
        ('assisted_devices','Artificial Limbs & Assisted Devices'),
        ('madaris','Madaris Support'),
        ('masjid','Masajid Support'),
        ('wedding','Wedding Support Program')],
        string='Transaction Type')
    cash_transaction_type = fields.Selection([
        ('scholarship','Scholarship'),
        ('kifalat','Kifalat Program'),
        ('rozgar','Rozgar Schemes')],
        string='Transaction Type')
    transaction_type = fields.Selection([
        ('ration','Ration Support'),
        ('ramzan','Ramzan Support'),
        ('meal','Meal Distribution'),
        ('medicines','Medicines - General'),
        ('medicines_cancer','Medicines - Cancer Support'),
        ('assisted_devices','Artificial Limbs & Assisted Devices'),
        ('madaris','Madaris Support'),
        ('masjid','Masajid Support'),
        ('wedding','Wedding Support Program'),
        ('scholarship','Scholarship'),
        ('kifalat','Kifalat Program'),
        ('rozgar','rozgar Schemes')],
        string='Transaction Type',compute="_compute_transaction_type", store=True)
    
    @api.constrains('authorized_person_cnic')
    def _check_authorized_person_cnic_format(self):
        for record in self:
            if record.authorized_person_cnic:
                if not re.match(r'^\d{5}-\d{7}-\d{1}$', record.authorized_person_cnic):
                    raise ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.authorized_person_cnic.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")

    @api.onchange('authorized_person_cnic')
    def _onchange_authorized_person_cnic(self):
        if self.authorized_person_cnic:
            cleaned_cnic = re.sub(r'[^0-9]', '', self.authorized_person_cnic)
            if len(cleaned_cnic) >= 13:
                self.authorized_person_cnic = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:12]}-{cleaned_cnic[12:]}"
            elif len(cleaned_cnic) > 5:
                self.authorized_person_cnic = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:]}"

    @api.constrains('head_cnic_no')
    def _check_head_cnic_no_format(self):
        for record in self:
            if record.head_cnic_no:
                if not re.match(r'^\d{5}-\d{7}-\d{1}$', record.head_cnic_no):
                    raise ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.head_cnic_no.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")

    @api.onchange('head_cnic_no')
    def _onchange_head_cnic_no(self):
        if self.head_cnic_no:
            cleaned_cnic = re.sub(r'[^0-9]', '', self.head_cnic_no)
            if len(cleaned_cnic) >= 13:
                self.head_cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:12]}-{cleaned_cnic[12:]}"
            elif len(cleaned_cnic) > 5:
                self.head_cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:]}"

    @api.constrains('member_cnic_no')
    def _check_member_cnic_no_format(self):
        for record in self:
            if record.member_cnic_no:
                if not re.match(r'^\d{5}-\d{7}-\d{1}$', record.member_cnic_no):
                    raise ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.member_cnic_no.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")

    @api.onchange('member_cnic_no')
    def _onchange_member_cnic_no(self):
        if self.member_cnic_no:
            cleaned_cnic = re.sub(r'[^0-9]', '', self.member_cnic_no)
            if len(cleaned_cnic) >= 13:
                self.member_cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:12]}-{cleaned_cnic[12:]}"
            elif len(cleaned_cnic) > 5:
                self.member_cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:]}"

    @api.constrains('father_cnic_no')
    def _check_father_cnic_no_format(self):
        for record in self:
            if record.father_cnic_no:
                if not re.match(r'^\d{5}-\d{7}-\d{1}$', record.father_cnic_no):
                    raise ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.father_cnic_no.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")

    @api.onchange('father_cnic_no')
    def _onchange_father_cnic_no(self):
        if self.father_cnic_no:
            cleaned_cnic = re.sub(r'[^0-9]', '', self.father_cnic_no)
            if len(cleaned_cnic) >= 13:
                self.father_cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:12]}-{cleaned_cnic[12:]}"
            elif len(cleaned_cnic) > 5:
                self.father_cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:]}"

    @api.depends('disbursement_type','in_kind_transaction_type','cash_transaction_type')
    def _compute_transaction_type(self):
        for rec in self:
            if rec.disbursement_type == 'in_kind':
                rec.transaction_type = rec.in_kind_transaction_type if rec.in_kind_transaction_type else ""
            elif rec.disbursement_type == 'cash':
                rec.transaction_type = rec.cash_transaction_type if rec.cash_transaction_type else ""
            else:
                rec.transaction_type = ""

    @api.depends('date_of_birth')
    def _compute_age(self):
        for record in self:
            if record.date_of_birth:
                # Get today's date
                today = fields.Date.today()
                age = today.year - record.date_of_birth.year
                record.age = age
            else:
                record.age = 0  # Default value when there's no birth date

    def _generate_random_barcode(self, is_donee, donor_type, is_employee, gender, birth_day):
        # raise exceptions.UserError(str(f'{birth_day} <-> {partner_type} <-> {logic_type}'))

        barcode = None

        if is_donee:
            RY = fields.Date.today().year
            BY = str(birth_day).split('-')[0]

            barcode = ''.join(random.choices(string.digits, k=7))  # Generate a 7-digit number

            check_digit = None

            today = fields.Date.today()
            age = today.year - int(BY)

            if is_employee and gender == 'female':
                check_digit = 2
            if is_employee and gender == 'male':
                check_digit = 3
            elif age > 18 and gender == 'female':
                check_digit = 0
            elif age > 18 and gender == 'male':
                check_digit = 1
            elif age < 18 and gender == 'female':
                check_digit = 4
            elif age < 18 and gender == 'male':
                check_digit = 5

            barcode = f'{str(RY)[2:]}-{str(BY)[2:]}-{barcode}-{check_digit}'
        else:
            RY = fields.Date.today().year

            barcode = ''.join(random.choices(string.digits, k=7))  # Generate a 7-digit number

            check_digit = None

            if is_employee:
                check_digit = 8
            elif donor_type == 'individual':
                check_digit = 6
            else:
                check_digit = 7

            barcode = f'{str(RY)}-{barcode}-{check_digit}'
            # barcode = f'{RY}{BY}{barcode}'

        return barcode
    
    def action_draft(self):
        self.active = True
        self.state = 'draft'
    
    def action_change_request(self):
        self.is_change_request = True
        self.state = 'change_request'
    
    def action_validate(self):
        if not self.mobile:
            raise exceptions.ValidationError(str(f'Please enter a Mobile Number'))

#	if self.email and not re.match(email_pattern, self.email):
#	    raise exceptions.ValidationError(str(f'Invalid Email {self.email}'))
        if self.mobile and (len(self.mobile) > 10 or len(self.mobile) < 0):
            raise exceptions.ValidationError(str(f'Invalid Mobile No. {self.mobile}'))
        elif self.cnic_no and not re.match(cnic_pattern, self.cnic_no):
            raise exceptions.ValidationError(str(f'Invalid CNIC No. {self.cnic_no}'))
        elif self.vat and not re.match(ntn_pattern, self.vat):
            raise exceptions.ValidationError(str(f'Invalid NTN No. {self.vat}'))
        elif self.date_of_birth and self.is_microfinance:
            today = fields.Date.today()

            # raise exceptions.ValidationError(str(vals.get('date_of_birth')))

            age = today.year - int(str(self.date_of_birth).split('-')[0])

            if age < 18:
                raise exceptions.ValidationError(str(f'Cannot register the Person for MicroFinance as his/her age is below 18'))

        if self.is_donee:
            res_partner = self.env['res.partner'].search(['|', ('cnic_no', '=', self.cnic_no), ('mobile', '=', self.mobile), ('is_donee', '=', self.is_donee), ('state', '=', 'register')])

            if res_partner:
                raise exceptions.ValidationError(str(f'A Donee with same CNIC or Mobile No. already exist in the System.'))
            
            res_partner = self.env['res.partner'].search(['|', ('cnic_no', '=', self.cnic_no), ('mobile', '=', self.mobile), ('is_donee', '=', False)])

            if res_partner:
                self.donor_id = res_partner.id
        else:
            res_partner = self.env['res.partner'].search([('phone_code_id', '=', self.phone_code_id.id), ('mobile', '=', self.mobile), ('is_donee', '=', self.is_donee), ('state', '=', 'register')])

            if res_partner:
                raise exceptions.ValidationError(str(f'A Donor with same Mobile No. already exist in the System.'))
        
            res_partner = self.env['res.partner'].search(['|', ('cnic_no', '=', self.cnic_no), ('mobile', '=', self.mobile), ('is_donee', '=', True)])

            if res_partner:
                self.donee_id = res_partner.id

        if not self.date_of_birth and self.is_donee:
            raise exceptions.ValidationError(str(f'Please specify the Date of Birth'))
        
        if self.donor_type == 'coorporate' and not self.is_donee:
            self.is_company = True
        
        self.barcode = self._generate_random_barcode(self.is_donee, self.donor_type, self.is_employee, self.gender, self.date_of_birth)
        
        if self.is_donee:
            res_partner = self.env['res.partner'].search(['|', ('cnic_no', '=', self.cnic_no), ('mobile', '=', self.mobile), ('is_donee', '=', False), ('state', '=', 'register')])

            if res_partner:
                res_partner.donee_id = self.id
        else:
            res_partner = self.env['res.partner'].search(['|', ('cnic_no', '=', self.cnic_no), ('mobile', '=', self.mobile), ('is_donee', '=', True), ('state', '=', 'register')])

            if res_partner:
                res_partner.donor_id = self.id

        if self.date_of_birth:
            if self.date_of_birth.year == fields.Date.today().year or self.date_of_birth.year > fields.Date.today().year:
                raise exceptions.ValidationError(str(f'Invalid Date of Birth'))

        self.state = 'validate'

        if not self.is_donee:
            self.action_register()

        if self.is_welfare:
            self.action_welfare_application()

    def action_reject(self):
        self.active = False
        self.state = 'reject'
    
    def action_register(self):
        if not self.date_of_birth and self.is_donee:
            raise exceptions.ValidationError(str(f'Please specify the Date of Birth'))
        

        if not self.barcode:
            self.barcode = self._generate_random_barcode(self.is_donee, self.donor_type, self.is_employee, self.gender, self.date_of_birth)

        self.state = 'register'
    
    def action_print_info(self):
        self.is_change_request = False
        self.state = 'print_info'

        report_action = self.env.ref('bn_profile_management.action_report_donee_form').report_action(self)
        return report_action

        # Printing the report

    def generate_microfinance_application(self):
        for scheme_type_id in self.scheme_type_ids:
            application = self.env['mfd.scheme.line'].search([('name', '=', scheme_type_id.name)], limit=1)

            loan_request = self.env['mfd.loan.request'].search([('scheme_id', '=', scheme_type_id.id), ('application_id', '=', application.id), ('customer_id', '=', self.id), ('state', 'not in', ['done', 'rejected'])])

            if not loan_request:
                mfd_lr =  self.env['mfd.loan.request'].create({
                    'scheme_id': scheme_type_id.id,
                    'application_id': application.id,
                    'customer_id': self.id
                })

                return mfd_lr.compute_asset_type()
    
    def generate_welfare_application(self):
        if self.disbursement_type_ids:
            for disbursement_type_id in self.disbursement_type_ids:
                disbursement_request = self.env['disbursement.request'].search([('disbursement_type_id', '=', disbursement_type_id.id), ('donee_id', '=', self.id), ('state', 'not in', ['disbursed', 'reject'])])

                if not disbursement_request and disbursement_request.order_type != 'recurring':
                    return self.env['disbursement.request'].create({
                        'disbursement_type_id': disbursement_type_id.id,
                        'donee_id': self.id
                    })
        else:
            return self.env['disbursement.request'].create({
                'donee_id': self.id
            })


    def action_microfinance_application(self):
        if self.state != 'register':
            raise exceptions.ValidationError('Please Register the Donee First...')

        if self.is_medical or self.is_student or self.is_employee or self.is_rider:
            raise exceptions.ValidationError('Only Applicable for Microfinance/Welfare...')

        if self.is_microfinance:
            self.generate_microfinance_application()

        report_action = self.env.ref('bn_profile_management.action_report_microfinance_application_form').report_action(self)
        return report_action
    
    def action_welfare_application(self):
        if self.state != 'register':
            raise exceptions.ValidationError('Please Register the Donee First...')

        if self.is_medical or self.is_student or self.is_employee or self.is_rider:
            raise exceptions.ValidationError('Only Applicable for Microfinance/Welfare...')
        
        if self.is_welfare:
            self.generate_welfare_application()

        # report_action = self.env.ref('bn_profile_management.action_report_welfare_application_form').report_action(self)
        # return report_action

    def auto_create_fee_voucher(self):
        students = self.env['res.partner'].search(['|', ('is_student','=',True), ('student','=',True)])

        fee_journal = self.env['account.journal'].search([('name','=','Student Fee')],limit=1)
        
        if not fee_journal:
            raise exceptions.ValidationError("Fee Journal not found")
        
        today = fields.Date.today()
        first_day_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        for student in students:
            product_ids = self.env['product.product'].browse(student.course_ids.ids)
            if not product_ids:
                raise exceptions.ValidationError("Course not found")
            
            for product_id in product_ids:
                fee_voucher = self.env['fee.box'].search([('partner_id', '=', student.id), ('create_date', '>', first_day_of_month)])
                
                if not fee_voucher:
                    self.env['fee.box'].create({
                        'registration_id': student.registration_id,
                        'partner_id': student.id,
                        'journal_id': fee_journal.id,
                        'course_id': product_id.id,
                        'date': fields.Date.today(),
                        'amount': product_id.lst_price,
                    })

class GuarantorInformation(models.Model):
    _name = 'guarantor.information'
    _description = 'Guarantor Information'


    partner_id = fields.Many2one('res.partner', string="Partner ID")

    name = fields.Char('Name')
    father_spouse_name = fields.Char('Father / Spouse Name')
    landline_no = fields.Char('Landline No.')
    address = fields.Char('Address')
    cnic_no = fields.Char('CNIC No.')
    mobile = fields.Char('Mobile No.', size=10)
    phone_code_id = fields.Many2one('res.country', string="Phone Code")

    relation = fields.Char('Relation')
    occupation = fields.Char('Occupation')

    @api.constrains('cnic_no')
    def _check_cnic_format(self):
        for record in self:
            if record.cnic_no:
                if not re.match(r'^\d{5}-\d{7}-\d{1}$', record.cnic_no):
                    raise ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.cnic_no.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")

    @api.onchange('cnic_no')
    def _onchange_cnic_no(self):
        if self.cnic_no:
            cleaned_cnic = re.sub(r'[^0-9]', '', self.cnic_no)
            if len(cleaned_cnic) >= 13:
                self.cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:12]}-{cleaned_cnic[12:]}"
            elif len(cleaned_cnic) > 5:
                self.cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:]}"


examination_selection = [
    ('matric', 'Matric'),
    ('inter', 'Inter'),
    ('under_graduate', 'Under Graduate'),
    ('graduate', 'Graduate'),
    ('post_grduate', 'Post Graduate'),
    ('master', 'Master'),
]

year_selection = [(str(year), str(year)) for year in range(2000, 2020)]

class StudentQualification(models.Model):
    _name = "student.qualification"
    _description = "Student Qualification"


    partner_id = fields.Many2one('res.partner', string="Partner ID")

    school_uni_center = fields.Char('School/Uni/Center')
    board = fields.Char('Board')

    examination = fields.Selection(selection=examination_selection, string="Examination")
    year = fields.Selection(selection=year_selection, string="Year")

    percentage = fields.Float('Percentage')


class WelfareQualification(models.Model):
    _name = "welfare.qualification"
    _description = "Welfare Requester Qualification"


    partner_id = fields.Many2one('res.partner', string="Partner ID")

    school_uni_center = fields.Char('School/Uni/Center')
    board = fields.Char('Board')

    examination = fields.Selection(selection=examination_selection, string="Examination")
    year = fields.Selection(selection=year_selection, string="Year")

    percentage = fields.Float('Percentage')

class MicrofinanceQualification(models.Model):
    _name = "microfinance.qualification"
    _description = "Microfinance Requester Qualification"


    partner_id = fields.Many2one('res.partner', string="Partner ID")

    school_uni_center = fields.Char('School/Uni/Center')
    board = fields.Char('Board')

    examination = fields.Selection(selection=examination_selection, string="Examination")
    year = fields.Selection(selection=year_selection, string="Year")

    percentage = fields.Float('Percentage')


class FamilyInformation(models.Model):
    _name = "family.information"
    _description = "Family Information"


    partner_id = fields.Many2one('res.partner', string="Partner ID")

    relation = fields.Char('Relation')
    education = fields.Char('Education')
    cnic_bform = fields.Char('CNIC / B Form')
    complete_name = fields.Char('Complete Name')
    monthly_income = fields.Char('Monthly Income')
    
    age = fields.Integer('Age')
