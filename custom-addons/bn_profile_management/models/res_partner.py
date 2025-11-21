from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import re

# CNIC regular expression
cnic_pattern = r'^\d{5}-\d{7}-\d{1}$'


general_selection = [
    ('yes', 'Yes'),
    ('no', 'No'),
]

gender_selection = [
    ('male', 'Male'),
    ('female', 'Female'),
]

religion_selection = [
    ('muslim', 'Muslim'),
    ('non_muslim', 'Non-Muslim'),
    ('syed', 'Syed'),
]

martial_status_selection = [
    ('married', 'Married'),
    ('un_married', 'Unmarried'),
    ('divorce', 'Divorce'),
]

state_selection = [
    ('draft', 'Draft'),
    ('print_info', 'Print Info'),
    ('register', 'Registered'),
    ('reject', 'Rejected'),
    ('change_request', 'Change Request'),
]


class ResPartner(models.Model):
    _inherit = 'res.partner'


    gender = fields.Selection(selection=gender_selection, string="Gender", tracking=True)
    religion = fields.Selection(selection=religion_selection, string="Religion", tracking=True)
    martial_status = fields.Selection(selection=martial_status_selection, string="Martial Status", tracking=True)
    has_cnic = fields.Selection(selection=general_selection, string="Has CNIC", default='yes', tracking=True)
    state = fields.Selection(selection=state_selection, string="State", default='draft', tracking=True)
    
    mobile = fields.Char(size=10)
    surname = fields.Char('Surname', tracking=True)
    cnic_no = fields.Char('CNIC No.', tracking=True)
    next_kin = fields.Char('Next Kin', tracking=True)
    spouse_name = fields.Char('Spouse Name', tracking=True)
    father_name = fields.Char('Father Name', tracking=True)
    head_cnic_no = fields.Char('Head CNIC No.', tracking=True)
    old_system_id = fields.Char('Old System ID', tracking=True)
    member_cnic_no = fields.Char('Member CNIC No.', tracking=True)
    father_cnic_no = fields.Char('Father CNIC No.', tracking=True)
    nearest_land_mark = fields.Char('Nearest Land Mark', tracking=True)
    reference_remarks = fields.Char('Reference / Remarks', tracking=True)
    bank_wallet_account = fields.Char('Bank / Wallet Account', tracking=True)
    primary_registration_id = fields.Char('Primary Registration ID', tracking=True)
    secondary_registration_id = fields.Char('Secondary Registration ID')

    cnic_back = fields.Char('CNIC Back', tracking=True)
    cnic_front = fields.Char('CNIC Front', tracking=True)
    approved_form = fields.Char('Approved Form', tracking=True)
    reference_letter = fields.Char('Reference Letter', tracking=True)

    cnic_back_image = fields.Binary('CNIC Back Image')
    cnic_front_image = fields.Binary('CNIC Front Image')
    approved_form_file = fields.Binary('Approved Form File')
    reference_letter_file = fields.Binary('Reference Letter File')

    cnic_expiration = fields.Date('CNIC Expiration')
    date_of_birth = fields.Date('Date Of Birth')
    
    details = fields.Text('Details')

    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")
    country_code_id = fields.Many2one('res.country', string="Phone Code")

    age = fields.Integer('Age',compute="_compute_age", store=True)

    is_change_request = fields.Boolean('Is Change Request')
    is_donor = fields.Boolean('Is Donor', compute="_set_is_donor", store=True)
    donee_required_fields = fields.Boolean('Donee Required Fields', compute="_set_donee_required_fields", store=True)


    @api.depends('name', 'category_id')
    def _set_donee_required_fields(self):
        for rec in self:
            rec.donee_required_fields = False

            if 'Donee' in rec.category_id.mapped('name') and 'Individual' in rec.category_id.mapped('name'):
                rec.donee_required_fields = True
    
    @api.depends('name', 'category_id')
    def _set_is_donor(self):
        for rec in self:
            rec.is_donor = False

            if 'Donor' in rec.category_id.mapped('name'):
                rec.is_donor = True

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

    @api.constrains('cnic_no')
    def _check_cnic_no_format(self):
        for record in self:
            if record.cnic_no:
                if not re.match(cnic_pattern, record.cnic_no):
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

    @api.constrains('member_cnic_no')
    def _check_member_cnic_no_format(self):
        for record in self:
            if record.member_cnic_no:
                if not re.match(cnic_pattern, record.member_cnic_no):
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
                if not re.match(cnic_pattern, record.father_cnic_no):
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
    
    @api.onchange('date_of_birth')
    def _onchange_date_of_birth(self):
        if self.date_of_birth:
            if self.date_of_birth.year == fields.Date.today().year or self.date_of_birth.year > fields.Date.today().year:
                raise ValidationError(str(f'Invalid Date of Birth...'))

    def action_print_info(self):
        self.is_change_request = False
        self.state = 'print_info'

        return self.env.ref('bn_profile_management.action_profile_management_report').report_action(self)
    
    def action_welfare_application(self):
        return self.env['welfare'].create({
            'donee_id': self.id
        })
    
    def action_register(self):
        if not self.date_of_birth and 'Donee' in self.category_id.mapped('name') and 'Individual' in self.category_id.mapped('name'):
            raise ValidationError('Please specify your Date of Birth...')
        elif self.date_of_birth and 'Microfinance' in self.category_id.mapped('name') and self.age and self.age < 18:
            raise ValidationError('Cannot register the Person for Microfinance as his/her age is below 18.')
        elif 'Donee' in self.category_id.mapped('name'):
            res_partner = self.env['res.partner'].search(['|', ('cnic_no', '=', self.cnic_no), ('mobile', '=', self.mobile), ('country_code_id', '=', self.country_code_id.id), ('category_id.name', 'in', ['Donee']), ('state', '=', 'register')])

            if res_partner:
                raise ValidationError(str(f'A Donee with same CNIC or Mobile No. already exist in the System.'))
            
            res_partner = self.env['res.partner'].search([('country_code_id', '=', self.country_code_id.id), ('mobile', '=', self.mobile), ('category_id.name', 'in', ['Donor']), ('state', '=', 'register')])

            if res_partner:
                self.secondary_registration_id = res_partner.primary_registration_id
            else:
                if self.cnic_no:
                    res_partner = self.env['res.partner'].search([('cnic_no', '=', self.cnic_no), ('category_id.name', 'in', ['Donor']), ('state', '=', 'register')])

                    if res_partner:
                        self.secondary_registration_id = res_partner.primary_registration_id
        elif 'Donor' in self.category_id.mapped('name'):
            res_partner = self.env['res.partner'].search([('country_code_id', '=', self.country_code_id.id), ('mobile', '=', self.mobile), ('category_id.name', 'in', ['Donor']), ('state', '=', 'register')])

            if res_partner:
                raise ValidationError(str(f'A Donor with same Mobile No. already exist in the System.'))
            
            res_partner = self.env['res.partner'].search([('country_code_id', '=', self.country_code_id.id), ('mobile', '=', self.mobile), ('category_id.name', 'in', ['Donee']), ('state', '=', 'register')])

            if res_partner:
                self.secondary_registration_id = res_partner.primary_registration_id
            else:
                if self.cnic_no:
                    res_partner = self.env['res.partner'].search([('cnic_no', '=', self.cnic_no), ('category_id.name', 'in', ['Donee']), ('state', '=', 'register')])

                    if res_partner:
                        self.secondary_registration_id = res_partner.primary_registration_id
        
        if not self.primary_registration_id:
            seq_num = None
            age = None
            BY = None
            
            RY = fields.Date.today().year
            RY = str(RY)[2:]

            if self.date_of_birth:
                BY = str(self.date_of_birth).split('-')[0]
                
                today = fields.Date.today()
                age = today.year - int(BY)

            check_digit = None

            if 'Donee' in self.category_id.mapped('name'):
                seq_num = self.env['ir.sequence'].next_by_code('donee_profile_management') or ('New')
                
                if 'Employee' in self.category_id.mapped('name') and self.gender == 'female':
                    check_digit = 2
                if 'Employee' in self.category_id.mapped('name') and self.gender == 'male':
                    check_digit = 3
                elif age > 18 and self.gender == 'female':
                    check_digit = 0
                elif age > 18 and self.gender == 'male':
                    check_digit = 1
                elif age < 18 and self.gender == 'female':
                    check_digit = 4
                elif age < 18 and self.gender == 'male':
                    check_digit = 5
            else:
                seq_num = self.env['ir.sequence'].next_by_code('donor_profile_management') or ('New')
                
                if 'Employee' in self.category_id.mapped('name'):
                    check_digit = 8
                elif 'Individual' in self.category_id.mapped('name'):
                    check_digit = 6
                else:
                    check_digit = 7

            self.primary_registration_id = f'{RY}-{str(BY)[2:]}-{seq_num}-{check_digit}' if 'Donee' in self.category_id.mapped('name') and 'Individual' in self.category_id.mapped('name') else f'{RY}-{seq_num}-{check_digit}'

        self.state = 'register'

        if 'Welfare' in self.category_id.mapped('name'):
            self.action_welfare_application()
    
    def action_change_request(self):
        self.is_change_request = True
        self.state = 'change_request'

    def action_reject(self):
        self.state = 'reject'

    def action_microfinance_application(self):
        pass