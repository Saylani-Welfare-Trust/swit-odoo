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
    cnic_no = fields.Char('CNIC No.', tracking=True, size=15)
    next_kin = fields.Char('Next Kin', tracking=True)
    spouse_name = fields.Char('Spouse Name', tracking=True)
    father_name = fields.Char('Father Name', tracking=True)
    head_cnic_no = fields.Char('Head CNIC No.', tracking=True, size=15)
    old_system_id = fields.Char('Old System ID', tracking=True)
    member_cnic_no = fields.Char('Member CNIC No.', tracking=True, size=15)
    father_cnic_no = fields.Char('Father CNIC No.', tracking=True, size=15)
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

            
            if not self.is_valid_cnic_format(self.member_cnic_no):
                raise ValidationError('Invalid CNIC No. format ( acceptable format XXXXX-XXXXXXX-X )')
    
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

            
            if not self.is_valid_cnic_format(self.father_cnic_no):
                raise ValidationError('Invalid CNIC No. format ( acceptable format XXXXX-XXXXXXX-X )')
    
    @api.onchange('date_of_birth')
    def _onchange_date_of_birth(self):
        if self.date_of_birth:
            if self.date_of_birth.year == fields.Date.today().year or self.date_of_birth.year > fields.Date.today().year:
                raise ValidationError(str(f'Invalid Date of Birth...'))

    def action_print_info(self):
        if self.is_change_request:
            self.state = 'draft'
        
        self.is_change_request = False

        return self.env.ref('bn_profile_management.action_profile_management_report').report_action(self)
    
    def action_welfare_application(self):
        return self.env['welfare'].create({
            'donee_id': self.id
        })
    
    def action_register(self):
        from dateutil.relativedelta import relativedelta
        
        # Step 1: Pre-fetch and cache all data needed for validations
        # Get category names for all records at once
        all_categories = {}
        for rec in self:
            all_categories[rec.id] = set(rec.category_id.mapped('name'))
        
        # Step 2: Early validations that can raise errors
        today = fields.Date.today()
        min_expiry_date = today + relativedelta(years=1)
        
        # Check for validation errors
        for rec in self:
            rec_categories = all_categories[rec.id]
            
            # Date of Birth validation for Donee+Individual
            if not rec.date_of_birth and 'Donee' in rec_categories and 'Individual' in rec_categories:
                raise ValidationError('Please specify your Date of Birth...')
            
            # Age validation for Microfinance
            if rec.date_of_birth and 'Microfinance' in rec_categories and rec.age and rec.age < 18:
                raise ValidationError('Cannot register the Person for Microfinance as his/her age is below 18.')
            
            # CNIC expiry validation for Donee
            if 'Donee' in rec_categories and rec.cnic_expiration and rec.cnic_expiration < min_expiry_date:
                raise ValidationError('CNIC expiry date should be minimum one year from the date of application. Please renew your CNIC before registration.')
        
        # Step 3: Batch database queries for duplicate checking
        # Collect all mobile numbers and CNICs
        all_mobiles = []
        all_cnics = []
        mobile_to_records = {}
        cnic_to_records = {}
        
        for rec in self:
            if rec.mobile:
                all_mobiles.append(rec.mobile)
                mobile_to_records.setdefault(rec.mobile, []).append(rec)
            if rec.cnic_no:
                all_cnics.append(rec.cnic_no)
                cnic_to_records.setdefault(rec.cnic_no, []).append(rec)
        
        # Single query to find all existing partners that might cause conflicts
        existing_partners = self.env['res.partner'].search([
            '|', ('mobile', 'in', all_mobiles),
            '|', ('cnic_no', 'in', all_cnics),
            ('state', '=', 'register')
        ])
        
        # Create lookup dictionaries for existing partners
        existing_mobile_to_partner = {}
        existing_cnic_to_partner = {}
        
        for partner in existing_partners:
            if partner.mobile and partner.country_code_id:
                key = (partner.country_code_id.id, partner.mobile)
                existing_mobile_to_partner[key] = partner
            if partner.cnic_no:
                existing_cnic_to_partner[partner.cnic_no] = partner
        
        # Step 4: Process duplicate checking and secondary registration assignment
        for rec in self:
            rec_categories = all_categories[rec.id]
            
            if 'Donee' in rec_categories:
                # Check for duplicate Donee
                if rec.mobile and rec.country_code_id:
                    key = (rec.country_code_id.id, rec.mobile)
                    partner = existing_mobile_to_partner.get(key)
                    if partner and 'Donee' in set(partner.category_id.mapped('name')):
                        raise ValidationError('A Donee with same CNIC or Mobile No. already exist in the System.')
                
                # Check for matching Donor for secondary registration
                secondary_assigned = False
                if rec.mobile and rec.country_code_id:
                    key = (rec.country_code_id.id, rec.mobile)
                    partner = existing_mobile_to_partner.get(key)
                    if partner and 'Donor' in set(partner.category_id.mapped('name')):
                        rec.secondary_registration_id = partner.primary_registration_id
                        secondary_assigned = True
                
                if not secondary_assigned and rec.cnic_no:
                    partner = existing_cnic_to_partner.get(rec.cnic_no)
                    if partner and 'Donor' in set(partner.category_id.mapped('name')):
                        rec.secondary_registration_id = partner.primary_registration_id
            
            elif 'Donor' in rec_categories:
                # Check for duplicate Donor
                if rec.mobile and rec.country_code_id:
                    key = (rec.country_code_id.id, rec.mobile)
                    partner = existing_mobile_to_partner.get(key)
                    if partner and 'Donor' in set(partner.category_id.mapped('name')):
                        raise ValidationError('A Donor with same Mobile No. already exist in the System.')
                
                # Check for matching Donee for secondary registration
                secondary_assigned = False
                if rec.mobile and rec.country_code_id:
                    key = (rec.country_code_id.id, rec.mobile)
                    partner = existing_mobile_to_partner.get(key)
                    if partner and 'Donee' in set(partner.category_id.mapped('name')):
                        rec.secondary_registration_id = partner.primary_registration_id
                        secondary_assigned = True
                
                if not secondary_assigned and rec.cnic_no:
                    partner = existing_cnic_to_partner.get(rec.cnic_no)
                    if partner and 'Donee' in set(partner.category_id.mapped('name')):
                        rec.secondary_registration_id = partner.primary_registration_id
        
        # Step 5: Generate primary registration IDs in batches
        # Group records by sequence type
        donee_records = []
        donor_records = []
        record_to_seq_type = {}
        
        for rec in self:
            rec_categories = all_categories[rec.id]
            if not rec.primary_registration_id:
                if 'Donee' in rec_categories:
                    donee_records.append(rec)
                    record_to_seq_type[rec.id] = 'donee'
                else:
                    donor_records.append(rec)
                    record_to_seq_type[rec.id] = 'donor'
        
        # Generate sequence numbers in batches
        sequence_numbers = {}
        
        # Generate for donee records
        if donee_records:
            seq_generator = self.env['ir.sequence'].next_by_code('donee_profile_management')
            # Note: In Odoo, sequences are typically generated one at a time
            # But we can still optimize by preparing all data first
            for rec in donee_records:
                sequence_numbers[rec.id] = self.env['ir.sequence'].next_by_code('donee_profile_management') or 'New'
        
        # Generate for donor records
        if donor_records:
            for rec in donor_records:
                sequence_numbers[rec.id] = self.env['ir.sequence'].next_by_code('donor_profile_management') or 'New'
        
        # Step 6: Calculate registration IDs
        RY = str(today.year)[2:]
        
        for rec in self:
            rec_categories = all_categories[rec.id]
            
            if not rec.primary_registration_id:
                seq_num = sequence_numbers.get(rec.id, 'New')
                check_digit = None
                BY_suffix = ""
                
                # Calculate age if date_of_birth exists
                age = None
                if rec.date_of_birth:
                    BY = str(rec.date_of_birth).split('-')[0]
                    BY_suffix = str(BY)[2:]
                    age = today.year - int(BY)
                
                if 'Donee' in rec_categories:
                    if 'Employee' in rec_categories and rec.gender == 'female':
                        check_digit = 2
                    elif 'Employee' in rec_categories and rec.gender == 'male':
                        check_digit = 3
                    elif age and age > 18 and rec.gender == 'female':
                        check_digit = 0
                    elif age and age > 18 and rec.gender == 'male':
                        check_digit = 1
                    elif age and age < 18 and rec.gender == 'female':
                        check_digit = 4
                    elif age and age < 18 and rec.gender == 'male':
                        check_digit = 5
                else:
                    if 'Employee' in rec_categories:
                        check_digit = 8
                    elif 'Individual' in rec_categories:
                        check_digit = 6
                    else:
                        check_digit = 7
                
                # Format the registration ID
                if 'Donee' in rec_categories and 'Individual' in rec_categories and BY_suffix:
                    rec.primary_registration_id = f'{RY}-{BY_suffix}-{seq_num}-{check_digit}'
                else:
                    rec.primary_registration_id = f'{RY}-{seq_num}-{check_digit}'
            
            # Update state
            rec.state = 'register'
        
        # Step 7: Handle post-registration actions
        # Process welfare applications
        welfare_records = [rec for rec in self if 'Welfare' in all_categories[rec.id]]
        for rec in welfare_records:
            rec.action_welfare_application()
        
        # Handle microfinance applications - return wizard for first record if needed
        microfinance_records = [rec for rec in self if 'Microfinance' in all_categories[rec.id]]
        if microfinance_records:
            # Return wizard for the first microfinance record
            return microfinance_records[0].action_print_microfinance_application()
        
        return True
    
    def action_change_request(self):
        self.is_change_request = True
        self.state = 'change_request'

    def action_reject(self):
        self.state = 'reject'

    def action_print_microfinance_application(self):
        if 'Microfinance' not in self.category_id.mapped('name'):
            raise ValidationError('This action is only restricted for Microfinance Application.')
        
        # Open wizard to select microfinance scheme
        return {
            'type': 'ir.actions.act_window',
            'name': 'Select Microfinance Scheme',
            'res_model': 'microfinance.application.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_profile_management.microfinance_application_wizard_form').id,
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
            }
        }