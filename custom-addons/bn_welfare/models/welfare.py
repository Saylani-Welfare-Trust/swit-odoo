from odoo import models, fields, _, api
from odoo.exceptions import ValidationError, UserError

import requests

import logging
from dateutil.relativedelta import relativedelta
import json

_logger = logging.getLogger(__name__)


assest_availability_selection = [
    ('not_available', 'Not Available'),
    ('available', 'Available')
]

residence_selection = [
    ('owned', 'Owned'),
    ('shared', 'Shared'),
    ('rented', 'Rented'),
]

general_selection = [
    ('no', 'No'),
    ('yes', 'Yes'),
]

loan_tenure_selection = [
    ('12M', '12 Months'),
    ('24M', '24 Months'),
    ('36M', '36 Months'),
    ('other', 'Other'),
]

state_selection = [
    ('draft', 'Draft'),
    ('completed', 'Completed'),
    ('send_for_inquiry', 'Send for Inquiry'),
    ('inquiry', 'Inquiry Officer'),
    ('committee_approval', 'Committee Approval'),
    ('hod_approve', 'HOD Approval'),
    ('mem_approve', 'Final Approval'),
    ('approve', 'Approved'),
    ('recurring', 'Recurring'),
    ('disbursed', 'Disbursed'),
    ('reject', 'Rejected'),
]

portal_sync_selection = [
    ('not_synced', 'Not Synced'),
    ('syncing', 'Syncing'),
    ('synced', 'Synced'),
    ('error', 'Sync Error'),
]

order_type_selection = [
    ('one_time', 'One Time'),
    ('recurring', 'Recurring'),
]

class Welfare(models.Model):
    _name = 'welfare'
    _description = "Welfare"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    order_type = fields.Selection(order_type_selection, string="Order Type")

    donee_id = fields.Many2one('res.partner', string="Donee")
    employee_id = fields.Many2one('hr.employee', string="Employee")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    is_individual = fields.Boolean('Is Individual', default=False) 
    employee_category_id = fields.Many2one('hr.employee.category', string="Employee Category", default=lambda self: self.env.ref('bn_welfare.inquiry_officer_hr_employee_category', raise_if_not_found=False).id)
    employee_category_id_officer = fields.Many2one(
        'hr.employee.category', 
        string="Employee Category", 
        default=lambda self: self.env.ref('bn_welfare.assigned_officer_hr_employee_category', raise_if_not_found=False).id if self.env.ref('bn_welfare.assigned_officer_hr_employee_category', raise_if_not_found=False) else False
    )
    
    name = fields.Char('Name', default="NEW")
    cnic_no = fields.Char(related='donee_id.cnic_no', string="CNIC No.", store=True, size=15)
    father_name = fields.Char(related='donee_id.father_name', string="Father Name", store=True)
    father_cnic_no = fields.Char(related='donee_id.father_cnic_no', string="Father CNIC No.", store=True, size=15)
    old_system_id = fields.Char('Old System ID')
    
    applicantLocationLink = fields.Char('Applicant Location Link') 
    date = fields.Date('Date', default=fields.Date.today())
    cnic_expiration_date = fields.Date(related='donee_id.cnic_expiration', string="CNIC Expiration Date", store=True)

    hod_remarks = fields.Text('HOD Remarks')
    member_remarks = fields.Text('Member Remarks')
    committee_remarks = fields.Text('Committee Remarks')
    rejection_remarks = fields.Text('Rejection Remarks')
    
    portal_last_sync_message = fields.Text('Portal Last Sync Message')

    application_form = fields.Binary('Application Form')
    application_form_name = fields.Char('Application Form Name')

    frc = fields.Binary('FRC')
    frc_name = fields.Char('FRC Name')
    

    electricity_bill_file = fields.Binary('Electricity Bill')
    electricity_bill_name = fields.Char('Electricity Bill Name')
    
    gas_bill_file = fields.Binary('Gas Bill')
    gas_bill_name = fields.Char('Gas Bill Name')
    
    family_cnic = fields.Binary('Family CNIC')
    family_cnic_name = fields.Char('Family CNIC Name')

    state = fields.Selection(selection=state_selection, string="State", default='draft')

    welfare_line_ids = fields.One2many('welfare.line', 'welfare_id', string="Welfare Lines")
    welfare_recurring_line_ids = fields.One2many('welfare.recurring.line', 'welfare_id', string="Welfare Lines")

    # Portal Details
    portal_application_id = fields.Char('Portal Application ID')
    portal_donee_id = fields.Char('Portal Donee ID')
    
    last_sync_date = fields.Datetime(string='Last Sync Date')

    is_synced = fields.Boolean('Is Synced')

    portal_sync_status = fields.Selection(selection=portal_sync_selection, string='Portal Sync Status', default='not_synced')

    portal_review_notes = fields.Text('Review Notes')
    inquiry_media = fields.Html(
        string="Inquiry Media",
        sanitize=False,   # IMPORTANT
    )
    required_approval_for_limit = fields.Selection([
        ('hod', 'HOD Approval Required'),
        ('member', 'Member Approval Required')
    ], string="Required Approval Based on Amount", compute="_compute_required_approval", store=False)


    # Employee Informaiton Fields
    designation = fields.Char('Designation') 
    company_name = fields.Char('Company Name') 
    company_phone = fields.Char('Company Phone No.') 
    company_address = fields.Char('Company Address')

    service_duration = fields.Integer('Service Duration ( In Years )')

    monthly_salary = fields.Monetary('Monthly Salary', currency_field='currency_id', default=0)

    # Education Information
    educaiton_line_ids = fields.One2many('microfinance.education', 'welfare_id', string="Educaiton Lines")

    # House Ownership / Residency Details
    residence_type = fields.Selection(selection=residence_selection, string="Residence Type")

    home_phone_no = fields.Char('Home Phone No.')
    landlord_cnic_no = fields.Char('CNIC No. of Landlord', size=15)
    landlord_mobile = fields.Char('Mobile No. of Landlord')
    landlord_name = fields.Char('Name of Landlord / Owner')
    
    rental_shared_duration = fields.Integer('Rental / Shared Duration')
    
    per_month_rent = fields.Float('Per month Rent')
    gas_bill = fields.Float('Cumulative Gas Bill of 6 Months (Total)')
    electricity_bill = fields.Float('Cumulative Electricity Bill of 6 Months (total)')
    
    home_other_info = fields.Text('Other info / Addres of Landlord')

    # Other Finance
    monthly_income = fields.Float('Monthly Income')
    outstanding_amount = fields.Float('Outstanding Amount')
    monthly_household_expense = fields.Float('Monthly Household Expenses')
    
    bank_account = fields.Selection(selection=general_selection, string="Bank Account")
    
    bank_name = fields.Char('Bank Name')
    account_no = fields.Char('Account No')
    institute_name = fields.Char('Institution Name')

    other_loan = fields.Selection(selection=general_selection, string="Any Other Loan?")

    # Other Information
    aid_from_other_organization = fields.Selection(selection=general_selection, string="Aid from Other Organisation")
    have_applied_swit = fields.Selection(selection=general_selection, string="Have you ever applied with SWIT?")

    details_1 = fields.Text('Details 1')
    details_2 = fields.Text('Details 2')
    
    driving_license = fields.Selection(selection=general_selection, string="Driving License")

    # Request Details
    # loan_request_amount = fields.Float('Loan Request Amount')

    # loan_request_amount = fields.Float(
    #     'Loan Request Amount',
    #     required=True
    # )

    loan_request_amount = fields.Float(
        string='Loan Request Amount',
        required=True,
        default=0.0
    )

    @api.constrains('loan_request_amount')
    def _check_loan_request_amount(self):
        for rec in self:
            if rec.loan_request_amount <= 0:
                raise ValidationError("Loan Request Amount must be greater than 0.")
    
    loan_tenure_expected = fields.Selection(selection=loan_tenure_selection, string='Loan Tenure Expected')

    security_offered = fields.Char('Security Offered')

    # Guarator Information
    guarantor_line_ids = fields.One2many('microfinance.guarantor', 'welfare_id', string='Guarator Lines')

    # Family Detail
    dependent_person = fields.Integer('No. of Dependents')
    household_member = fields.Integer('Household members')

    family_line_ids = fields.One2many('microfinance.family', 'welfare_id', string='Family Lines')

    # Add these fields if not already present
    institution_category = fields.Selection([
        ('masjid', 'Masjid'),
        ('madrasa', 'Madrasa'),
    ], string='Institution Category')
    
    subcategory = fields.Char(string='Subcategory')
    
    # Relationships
    committee_member_ids = fields.One2many(
        'welfare.committee.member', 
        'welfare_id', 
        string='Committee Members'
    )
    
    teacher_ids = fields.One2many(
        'welfare.teacher', 
        'welfare_id', 
        string='Teachers'
    )
    
    inquiry_report_ids = fields.One2many(
        'welfare.inquiry.report', 
        'welfare_id', 
        string='Inquiry Reports'
    )
    
    masjid_id = fields.One2many(
        'welfare.masjid', 
        'welfare_id', 
        string='Masjid Details'
    )
    
    madrasa_id = fields.One2many(
        'welfare.madrasa', 
        'welfare_id', 
        string='Madrasa Details'
    )
    
    # Inquiry Committee Questions Tab
    applicant_occupation = fields.Char('Applicant Occupation / Source of Income', tracking=True)
    residence_ownership = fields.Selection([
        ('owned', 'Owned'),
        ('rented', 'Rented'),
        ('shared', 'Shared'),
    ], string='Residence Ownership', tracking=True)
    total_children = fields.Integer('Total Number of Children', tracking=True)
    boys_count = fields.Integer('Number of Boys', tracking=True)
    girls_count = fields.Integer('Number of Girls', tracking=True)
    children_education_status = fields.Text('Children Education Status', tracking=True, 
        help="Specify whether children are studying in school, college, or university")
    main_issue = fields.Text('Main Issue/Problem', tracking=True, 
        help="Describe the main issue or problem being faced by the applicant or their family")
    
    # Previous Disbursements for same Donee
    previous_welfare_ids = fields.One2many(
        compute='_compute_previous_welfare_ids',
        comodel_name='welfare',
        string='Previous Disbursements to This Donee',
        store=False
    )
    
    previous_disbursement_id = fields.Many2one(
        compute='_compute_previous_disbursement_id',
        comodel_name='welfare',
        string='Most Recent Previous Disbursement',
        store=False,
        help='Link to the most recent previous disbursement for this donee'
    )
    
    show_disburse_button = fields.Boolean(
        compute="_compute_show_disburse_button",
        store=False
    )
    employee_domain = fields.Char(compute="_compute_employee_domain")
        # Inquiry Committee Questions Fields
    donee_house_status = fields.Char(
        string="Residential Status", 
        help="Does he own the house or live in a rented house?"
    )

    num_of_children = fields.Char(
        string="Number of Children"
    )

    num_of_sons = fields.Char(
        string="Number of Sons"
    )

    num_of_daughters = fields.Char(
        string="Number of Daughters"
    )

    children_education = fields.Char(
        string="Children's Education", 
        help="Where do the children study? (School, College, or University)"
    )

    donee_issues = fields.Text(
        string="Donee Issues", 
        help="What are the issues/concerns related to the donee?"
    )
    def _compute_required_approval(self):
        for rec in self:
            if rec._check_amount_within_hod_limit():
                rec.required_approval_for_limit = 'hod'
            else:
                rec.required_approval_for_limit = 'member'
    @api.depends('donee_id.area', 'employee_category_id')
    def _compute_employee_domain(self):
        for record in self:
            domain = []

            if record.employee_category_id:
                domain.append(('category_ids', 'in', [record.employee_category_id.id]))

            if record.donee_id and record.donee_id.area:
                domain.append(('area', '=', record.donee_id.area.id))

            record.employee_domain = json.dumps(domain)
    @api.depends('donee_id')
    def _compute_previous_welfare_ids(self):
        """Compute previous welfare disbursements for the same donee"""
        for rec in self:
            if rec.donee_id:
                domain = [
                    ('donee_id', '=', rec.donee_id.id),
                    ('state', 'in', ['disbursed', 'recurring'])
                ]
                # Only exclude current record if it has a real integer ID (saved record)
                if rec.id and isinstance(rec.id, int) and rec.id > 0:
                    domain.append(('id', '!=', rec.id))
                previous = self.search(domain, order='date desc')
                rec.previous_welfare_ids = previous
            else:
                rec.previous_welfare_ids = False

    @api.depends('donee_id')
    def _compute_previous_disbursement_id(self):
        """Compute the most recent previous disbursement for the same donee"""
        for rec in self:
            if rec.donee_id:
                domain = [
                    ('donee_id', '=', rec.donee_id.id),
                    ('state', 'in', ['disbursed', 'recurring'])
                ]
                # Only exclude current record if it has a real integer ID (saved record)
                if rec.id and isinstance(rec.id, int) and rec.id > 0:
                    domain.append(('id', '!=', rec.id))
                previous = self.search(domain, order='date desc', limit=1)
                rec.previous_disbursement_id = previous[0] if previous else False
            else:
                rec.previous_disbursement_id = False

    @api.onchange('donee_id')
    def _onchange_donee_id_populate_data(self):
        """Auto-populate form data from most recent previous welfare record for existing donee"""
        if not self.donee_id:
            return

        # Build domain for previous welfare records
        domain = [
            ('donee_id', '=', self.donee_id.id),
            ('state', 'in', ['disbursed', 'recurring', 'approve', 'inquiry', 'committee_approval'])
        ]
        
        # Exclude current record only if it is already saved (has a real integer ID)
        if self.id and isinstance(self.id, int) and self.id > 0:
            domain.append(('id', '!=', self.id))
        
        previous_welfare = self.search(domain, order='date desc', limit=1)

        if previous_welfare:
            # Auto-populate all fields (same as your original code)
            self.applicant_occupation = previous_welfare.applicant_occupation
            self.residence_ownership = previous_welfare.residence_ownership
            self.total_children = previous_welfare.total_children
            self.boys_count = previous_welfare.boys_count
            self.girls_count = previous_welfare.girls_count
            self.children_education_status = previous_welfare.children_education_status
            self.main_issue = previous_welfare.main_issue
            
             # Auto-populate residence/house info

            self.residence_type = previous_welfare.residence_type
            self.home_phone_no = previous_welfare.home_phone_no
            self.landlord_name = previous_welfare.landlord_name
            self.landlord_cnic_no = previous_welfare.landlord_cnic_no
            self.landlord_mobile = previous_welfare.landlord_mobile
            self.rental_shared_duration = previous_welfare.rental_shared_duration
            self.per_month_rent = previous_welfare.per_month_rent
            self.gas_bill = previous_welfare.gas_bill
            self.electricity_bill = previous_welfare.electricity_bill
            self.home_other_info = previous_welfare.home_other_info
                      
             # Auto-populate financial info

            self.monthly_income = previous_welfare.monthly_income
            self.outstanding_amount = previous_welfare.outstanding_amount
            self.monthly_household_expense = previous_welfare.monthly_household_expense
            self.bank_account = previous_welfare.bank_account
            self.bank_name = previous_welfare.bank_name
            self.account_no = previous_welfare.account_no
            self.other_loan = previous_welfare.other_loan
            self.institute_name = previous_welfare.institute_name
            
            # Auto-populate employment info

            self.designation = previous_welfare.designation
            self.company_name = previous_welfare.company_name
            self.company_phone = previous_welfare.company_phone
            self.company_address = previous_welfare.company_address
            self.service_duration = previous_welfare.service_duration
            self.monthly_salary = previous_welfare.monthly_salary
            # Auto-populate document fields
            self.frc = previous_welfare.frc
            self.application_form = previous_welfare.application_form
            self.electricity_bill_file = previous_welfare.electricity_bill_file
            self.gas_bill_file = previous_welfare.gas_bill_file
            self.family_cnic = previous_welfare.family_cnic
            
            # Auto-populate family info
            self.dependent_person = previous_welfare.dependent_person
            self.household_member = previous_welfare.household_member
            
            # Show notification about auto-population

            return {
                'warning': {
                    'title': 'Data Auto-Populated',
                    'message': f'Form has been automatically populated with data from previous application dated {previous_welfare.date}.\n\nPrevious Disbursements can be viewed in the "Previous Disbursements" tab.'
                }
            }
    @api.model
    def _auto_disburse_if_all_lines_delivered(self):
        records = self.search([('state', 'in', ['recurring', 'approve'])])
        for rec in records:
            if rec.order_type == 'one_time':
                lines = rec.welfare_line_ids
                if lines and all(l.state == 'disbursed' for l in lines):
                    rec.state = 'disbursed'
            elif rec.order_type == 'recurring':
                lines = rec.welfare_recurring_line_ids
                if lines and all(l.state == 'disbursed' for l in lines):
                    rec.state = 'disbursed'
    
    def _compute_show_disburse_button(self):
        for rec in self:
            
            has_recurring = rec.order_type == 'recurring'

            # Visibility logic
            if has_recurring:
                # Show ONLY in recurring state
                rec.show_disburse_button = rec.state == 'recurring'
            else:
                # Show ONLY in approve state
                rec.show_disburse_button = rec.state == 'approve'

    # Add this method to handle data parsing
    def _parse_form_data(self, rec):
        """Parse form data based on category"""
        form_data = rec.get('form', {})
        category = rec.get('category')
        subcategory = rec.get('subCategory')
        
        data = {
            'institution_category': category,
            'subcategory': subcategory,
        }
        
        if category == 'masjid':
            data.update(self._parse_masjid_data(form_data))
        elif category == 'madrasa':
            data.update(self._parse_madrasa_data(form_data))
            
        return data
    
    def _parse_masjid_data(self, form_data):
        """Parse masjid specific data"""
        masjid_info = form_data.get('masjidInfo', {})
        prayers_info = form_data.get('prayersInfo', {})
        fund_info = form_data.get('fundInfo', {})
        account_details = form_data.get('accountDetails', {})
        
        return {
            'institute_name': masjid_info.get('masjidName'),
            'company_address': masjid_info.get('address'),
            'city': masjid_info.get('city'),
            'district': masjid_info.get('district'),
        }
    
    def _parse_madrasa_data(self, form_data):
        """Parse madrasa specific data"""
        madrasa_info = form_data.get('madrasaInfo', {})
        fund_info = form_data.get('fundInfo', {})
        account_details = form_data.get('accountDetails', {})
        
        return {
            'institute_name': madrasa_info.get('madarsaName'),
            'company_address': madrasa_info.get('address'),
            'city': madrasa_info.get('city'),
            'district': madrasa_info.get('district'),
        }
    
    def _to_float(self, value):
        """Convert string to float safely"""
        try:
            return float(value) if value else 0.0
        except:
            return 0.0
    
    def _to_int(self, value):
        """Convert string to int safely"""
        try:
            return int(float(value)) if value else 0
        except:
            return 0
    
    def _to_bool(self, value):
        """Convert Yes/No string to boolean"""
        return str(value).lower() == 'yes' if value else False



    @api.model
    def create(self, vals):
        if vals.get('name', _('NEW')) == _('NEW'):
            vals['name'] = self.env['ir.sequence'].next_by_code('welfare') or _('New')
        
        return super().create(vals)
    
    def clean_url(self, url) :
        return (
            url.strip()
            .replace('\u200b', '')   # zero-width space
            .replace('\ufeff', '')   # BOM
            .replace('\u00a0', '')   # non-breaking space
        )

    
    def _make_sadqa_api_call(self, endpoint, method='POST', data=None):
        """Make API call to Sadqa Jaria portal"""
        # base_url = 'https://backend.switsjmm.com'
        url = f"{self.env.company.welfare_url}{endpoint}"
        headers = self._get_sadqa_api_headers()

        url = self.clean_url(url)
        # raise UserError(
        #         "URL:\n%s\n\nHeaders:\n%s\n\nData:\n%s"
        #         % (url, headers, data)
        #     )
        if data is not None:
            try:
                # Convert non-serializable types (dates, datetimes, Decimals, etc.) to JSON-safe values
                data = json.loads(json.dumps(data, default=str))
            except Exception as e:
                _logger.error("Failed to prepare JSON payload: %s", e)
                raise UserError(_("Failed to prepare request payload: %s") % e)
        # raise UserError(
        #     f"API Request Failed\n\n"
        #     f"URL: {url}\n"
        #     f"Headers: {headers}"
        #     f"Data: {data}\n"
        # )
        _logger.info(f"Making Sadqa Jaria API call to {url} with method {method} and data: {data}")
        try:
            if data is None :
                response = requests.post(url, headers=headers, timeout=30)
            else :
                response = requests.post(url, headers=headers, json=data, timeout=30)

            
            response.raise_for_status()
            result = response.json()
            _logger.info(f" URL: {url} Data: {data}  api response : {result}")
            # raise ValidationError(str(result))

            
            if not result.get('json', {}):
                error_msg = result.get('error', 'Unknown error occurred')
                raise Exception(f"Portal API Error: {error_msg}")
            # raise exceptions.ValidationError(str("result",result))
                
            return result.get('json', {})
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"Sadqa Jaria API Request failed: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            _logger.error(f"Sadqa Jaria API Processing failed: {str(e)}")
            raise e
    
    def _check_donee_exists_in_portal(self):
        """Check if donee already exists in portal"""
        try:
            data={
                    "json":{
                    "odooId": self.donee_id.id
                    }
                }    
            _logger.info(f"Donee checking query peremeters: {data}")
            result = self._make_sadqa_api_call(f'{self.env.company.check_donee_endpoint}','POST', data) # type: ignore
            # _logger.info(f"Donee found in portal: {result}")
            # raise UserError(str(result))
            return result
        except Exception as e:
            _logger.info(f"Donee not found in portal: {str(e)}")
            return None

    def action_check_portal_status(self):
        """Check current status in portal"""
        self.ensure_one()
        
        # try:
            # Check if donee exists
        donee_data = self._check_donee_exists_in_portal()
        # _logger.info(f"Donee data: {donee_data}")

        # raise exceptions.ValidationError(donee_data)

            
        if donee_data:
                message = f"✅ Donee exists in portal. Name: {donee_data.get('name')}"

        else:
            donee_in_portal = self._create_donee_in_portal()
        # Check for applications
        application = self._search_portal_applications()
        # _logger.info(f"Applications found: {application}")    
        app_state = application.get('status') if application else None
        inquiry_reports = application.get('inquiryReports') if application else None
        all_media = []
        all_remarks = []
        if isinstance(inquiry_reports, list):
            for report in inquiry_reports:
                media = report.get('media') if isinstance(report, dict) else None
                remarks = report.get('remarks') if isinstance(report, dict) else None
                if media:
                    for url in media:
                        all_media.append(f'<a href="{url}" target="_blank">View Image</a>')
                if remarks:
                    all_remarks.append(remarks)
        # raise UserError(f"media: {media}, proccessedMedia: {all_media}")
        if app_state == 'inquiry_complete': # type: ignore
            self.write({"inquiry_media": '<br/>'.join(all_media) if all_media else ''})
            self.write({"portal_review_notes": '\n'.join(all_remarks) if all_remarks else '' })
            self.write({"state":"inquiry"})
            result = self._handle_existing_application(application)
            message = f" | 📋 application status: {app_state} "
            message += f" | 📋 {result['message']} "
        else:
            message += f" | 📋 No applications found"     # type: ignore
        return self._show_notification('Portal Status Check', message, 'info')
    
    def _find_matching_application(self, applications):
        """Find matching application from portal data"""
        for app in applications:
            # Match by CNIC (most reliable)
            # _logger.info(f"Checking application: {app} and id is system {self.id} portal {app.get('id')}" )
            if app.get('odooId') == self.id and app.get('department') == "welfare":
                return app
            # # Match by name and WhatsApp
            # if (app.get('name') == self.donee_id.name and 
            #     app.get('whatsapp') == self.donee_id.mobile):
            #     return app
        return None
    
    def _search_portal_applications(self):
        """Search for matching applications in portal"""
        try:
            result = self._make_sadqa_api_call(self.env.company.search_endpoint)
            applications = result
            
            if applications:
                _logger.info(f"Unsynced applications found: {applications}")
                # Find matching application based on donee information
                matching_app = self._find_matching_application(applications)
                return matching_app
            return None
            
        except Exception as e:
            _logger.warning(f"No unsynced applications found: {str(e)}")
            return None

    def _mark_application_synced(self):
        """Mark application as synced in portal"""
        data = {
                "json":{

                "odooId": self.id,
                "department": "welfare"
            }
        }
        result = self._make_sadqa_api_call(self.env.company.mark_application_endpoint, 'POST', data)
        return result

    def _handle_existing_application(self, portal_application):
        """Handle existing application found in portal"""
        # Mark application as synced in portal
        synced_application = self._mark_application_synced()
        
        # Update disbursement record with portal information
        # self.write({
        #     'portal_application_id': portal_application.get('id'),
        #     'portal_donee_id': portal_application.get('doneeId', ''),
        #     'is_synced': True,
        #     'last_sync_date': fields.Datetime.now(),
        #     # 'portal_review_notes': portal_application.get('reviewNotes', '') or portal_application.get('notes', '')
        # })
        
        return {
            'action': 'linked_existing',
            'application_id': portal_application.get('id'),
            'message': f"✅ Existing application linked successfully. Application ID: {portal_application.get('id')}",
            'details': f"Donee: {portal_application.get('name')}"
        }
    
    def _create_donee_in_portal(self):
        """Create donee in Sadqa Jaria portal"""
        data = {
                "json":{
                "name": self.donee_id.name or '',
                "whatsapp": self.donee_id.mobile or '',
                "cnic": (
                    self.donee_id.cnic_no.replace("-", "")
                    if self.donee_id.cnic_no else ""
                ),            
                "odooId": self.donee_id.id
            }
        }
        # raise UserError(str(data))
        result = self._make_sadqa_api_call(self.env.company.create_donee_endpoint, 'POST', data)
        return result

    def create_portal_application(self):
        """Create application in Sadqa Jaria portal"""
        # self.ensure_one()
        data = {
            "json": {
                "applicationData": {
                    "odooId": self.id,
                    "doneeOdooId": self.donee_id.id,
                    "inquiryOfficerOdooId": self.employee_id.id,
                    "department": "welfare",
                    "form": {
                        "category": "welfare",  # fix
                        "subcategory": "welfare",
                        "date": str(self.date) if self.date else None,
                        "loanRequestAmount": self.loan_request_amount,
                        "applicantInformation": {
                            "name": self.donee_id.name,
                            "fatherName": self.father_name,
                            "cnic": self.cnic_no,
                            "phoneNumber": self.donee_id.mobile,
                            "whatsappNumber": self.donee_id.mobile,
                            "applicantLocationLink": self.applicantLocationLink
                        },
                        "employmentInfo": {
                            "companyName": self.company_name,
                            "companyAddress": self.company_address,
                            "companyPhone": self.company_phone,
                            "designation": self.designation,
                            "durationOfService": self.service_duration,
                            "monthlySalary": self.monthly_salary
                        },
                        "residencyInfo": {
                            "residenceType": self.residence_type,
                            "homePhone": self.home_phone_no,
                            "landlordName": self.landlord_name,
                            "landlordCnic": self.landlord_cnic_no,
                            "landlordMobile": self.landlord_mobile,
                            "rentalDuration": self.rental_shared_duration,
                            "monthlyRent": self.per_month_rent,
                            "gasBill": self.gas_bill,
                            "electricityBill": self.electricity_bill,
                            "otherInfo": self.home_other_info
                        }
                    }
                }
            }
        }
        # raise UserError(str(data))
        result = self._make_sadqa_api_call(
            self.env.company.create_application_endpoint,  # endpoint from res.company
            'POST',
            data
        )
        return result


    def _handle_new_application(self, existing_donee):
        """Handle creation of new application/donee in portal"""
        donee_data = None
        
        if not existing_donee:
            # Create new donee in portal
            donee_data = self._create_donee_in_portal()
        portal_application = self.create_portal_application()
        portal_application_id = portal_application.get('id')
        
        
        # Update disbursement record with portal information
        update_vals = {
            'portal_donee_id': donee_data.get('id') if donee_data else existing_donee.get('id'),
            'is_synced': True,
            'last_sync_date': fields.Datetime.now(),
            'portal_application_id': portal_application_id
        }
        
        self.write(update_vals)
        
        action = 'created_donee' if not existing_donee else 'linked_existing_donee'
        message = "✅ New donee created in portal" if not existing_donee else "✅ Existing donee linked in portal "
        message += f" | 📋 Application created with ID: {portal_application_id} " if portal_application_id else f" Portal application not created Error {portal_application.get('code', 'Unknown error')}"
        
        return {
            'action': action,
            'donee_id': donee_data.get('id') if donee_data else existing_donee.get('id'),
            'message': message,
            'details': f"Donee ID: {donee_data.get('id') if donee_data else existing_donee.get('id')}"
        }
    
    def _update_sync_status_success(self, result):
        """Update successful sync status"""
        self.write({
            'portal_sync_status': 'synced',
            'portal_last_sync_message': f"Success: {result['message']} at {fields.Datetime.now()}"
        })

    def _create_sync_chatter_message(self, result):
        """Create chatter message for sync activity"""
        message_body = f"""
        <b>🔄 Sadqa Jaria Portal Sync Completed</b>
        <br/>
        <b>Action:</b> {result['action'].replace('_', ' ').title()}
        <br/>
        <b>Status:</b> ✅ Success
        <br/>
        <b>Message:</b> {result['message']}
        <br/>
        <b>Details:</b> {result.get('details', 'N/A')}
        <br/>
        <b>Sync Date:</b> {fields.Datetime.now()}
        """
        
        self.message_post(body=message_body)

    def _show_notification(self, title, message, type='info'):
        """Show notification to user"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': type,
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},

            }
        }
    
    def _get_sadqa_api_headers(self):
        """Get API authentication headers"""
        return {
            'x-odoo-auth-key': f'{self.env.company.odoo_auth_key}',
            'Content-Type': 'application/json'
        }

    def action_send_for_inquiry(self):
        """Send for Inquiry - No automatic routing"""
        if not self:
            raise UserError("Please select at least one record.")
        
        invalid = self.filtered(lambda r: r.state != 'completed')
        if invalid:
            raise UserError("Some selected records are not completed and cannot be processed.")
        
        # Your existing portal sync code...
        success_msgs = []
        error_msgs = []
        
        for rec in self:
            if not rec.name:
                error_msgs.append(f"[{rec.display_name}] Donee name is required.")
                continue
            if not rec.cnic_no and not rec.donee_id.mobile:
                error_msgs.append(f"[{rec.display_name}] CNIC or WhatsApp/Mobile is required.")
                continue
            try:
                rec.write({
                    'portal_sync_status': 'syncing',
                    'portal_last_sync_message': f"Sync started at {fields.Datetime.now()}",
                    'state': 'send_for_inquiry'  # Just move to send_for_inquiry
                })
                # Your existing sync logic...
                existing_donee = rec._check_donee_exists_in_portal()
                result = rec._handle_new_application(existing_donee)
                rec._update_sync_status_success(result)
                rec._create_sync_chatter_message(result)
                success_msgs.append(f"[{rec.display_name}] {result['message']}")
            except Exception as e:
                error_message = f"[{rec.display_name}] Portal sync failed: {str(e)}"
                rec.write({
                    'portal_sync_status': 'error',
                    'portal_last_sync_message': error_message,
                    'is_synced': False
                })
                rec.message_post(body=f"❌ {error_message}")
                error_msgs.append(error_message)
        
        # Show results
        summary = ""
        if success_msgs:
            summary += "<b>Success:</b><br/>" + "<br/>".join(success_msgs) + "<br/>"
        if error_msgs:
            summary += "<b>Errors:</b><br/>" + "<br/>".join(error_msgs)
        if not summary:
            summary = "No records processed."
        
        return self._show_notification('Send for Inquiry Results', summary, 'info')

    
    def action_move_to_hod(self):
        """HOD Approval - No limit check here"""
        for record in self:
            if not record.hod_remarks:
                raise ValidationError('Please enter HOD Remarks!')
            
            # No limit check - just move to HOD approval
            record.state = 'hod_approve'
    
    def action_move_to_member(self):
        """Member Approval - No limit check here"""
        for record in self:
            if not record.member_remarks:
                raise ValidationError('Please enter Member Remarks!')
            
            # No limit check - just move to member approval
            record.state = 'mem_approve'
    
    def action_approve(self):
        """Final approval logic"""
        for record in self:
            if record.order_type == 'recurring':
                for line in record.welfare_line_ids:
                    if self.env['welfare.recurring.line'].search_count([
                        ('donee_id', '=', record.donee_id.id),
                        ('disbursement_category_id', '=', line.disbursement_category_id.id),
                        ('state', '=', 'draft')
                    ]):
                        pass
            
            record.state = 'approve'
        
        # Print report
        return self.env.ref('bn_welfare.action_report_welfare_collection_document').report_action(self)
    
    # def action_move_to_hod(self):

    #     if not self.hod_remarks:
    #         raise ValidationError('Please enter HOD Remarks!')
        
    #     self.state = 'hod_approve'
    
    # def action_move_to_member(self):
    #     if not self.member_remarks:
    #         raise ValidationError('Please enter Member Remarks!')
        
    #     self.state = 'mem_approve'
    
    # def action_approve(self):
    #     if self.order_type == 'recurring':
    #         for line in self.welfare_line_ids:
    #             if self.env['welfare.recurring.line'].search_count([
    #                 ('donee_id', '=', self.donee_id.id),
    #                 ('disbursement_category_id', '=', line.disbursement_category_id.id),
    #                 ('state', '=', 'draft')
    #             ]):
    #                 pass
    #     self.state = 'approve'

    #     # Trigger the welfare collection report for printing/giving to the person
    #     return self.env.ref('bn_welfare.action_report_welfare_collection_document').report_action(self)

    def action_reject(self):
        if not self.rejection_remarks:
            raise ValidationError('Please enter Rejection Remarks before rejection.')
        self.state = 'reject'

    def action_create_recurring_order(self):
        for line in self.welfare_line_ids:
            # if line.order_type != 'recurring':
            #     raise ValidationError('This request does not belong to recurring order.')
            if self.order_type != 'recurring':
                raise ValidationError('This request does not belong to recurring order.')
            
            if line.recurring_duration:
                month = 0
                num_months = int(line.recurring_duration.split('_')[0])
                
                # Get available advance donation lines if advance donation is linked to welfare line
                            
                for i in range(num_months):
                    recurring_line_vals = {
                        'welfare_id': line.welfare_id.id,
                        'collection_date': line.collection_date + relativedelta(months=month),
                        'product_id': line.product_id.id,
                        'currency_id': line.currency_id.id,
                        'analytic_account_id': line.analytic_account_id.id,
                        'disbursement_category_id': line.disbursement_category_id.id,
                        'disbursement_application_type_id': line.disbursement_application_type_id.id,
                        'quantity': line.quantity,
                        'collection_point': line.collection_point,
                        'amount': line.total_amount,
                        # 'advance_donation_id': line.advance_donation_id.id if line.advance_donation_id.id else None,
                    }
                    
                    self.env['welfare.recurring.line'].create(recurring_line_vals)
                    month += 1

        self.state = 'recurring'

    
    def action_committee_approval(self):
        """Committee Approval - Check limits here"""
        for record in self:
            # Check if amount exceeds HOD limit
            within_limit = record._check_amount_within_hod_limit()
            
            if not within_limit:
                # Amount exceeds HOD limit, add warning/note
                record.message_post(body="""
                    <b>⚠️ Amount Limit Notice</b><br/>
                    Request amount ({}) exceeds HOD limit. 
                    This request will require Member Approval instead of HOD Approval.
                """.format(record.loan_request_amount))
            
            # Your existing committee approval validations
            if not record.committee_remarks:
                raise ValidationError(_('Please enter Committee Remarks before approval.'))
            
            # Document validation
            missing_fields = []
            if not record.application_form:
                missing_fields.append("Application Form")
            if not record.electricity_bill_file:
                missing_fields.append("Electricity Bill")
            if not record.gas_bill_file:
                missing_fields.append("Gas Bill")
            if not record.family_cnic:
                missing_fields.append("Family CNIC")
            
            if missing_fields:
                raise ValidationError(_(
                    "Please upload the following documents before approval:\n- %s"
                ) % ("\n- ".join(missing_fields)))
            
            # Set state to committee_approval
            record.state = 'committee_approval'
        
    # def action_committee_approval(self):
    #     for record in self:

    #         # Remarks check
    #         if not record.committee_remarks:
    #             raise ValidationError(_('Please enter Committee Remarks before approval.'))

    #         # Document validation
    #         missing_fields = []

    #         if not record.application_form:
    #             missing_fields.append("Application Form")
    #         if not record.electricity_bill_file:
    #             missing_fields.append("Electricity Bill")
    #         if not record.gas_bill_file:
    #             missing_fields.append("Gas Bill")
    #         if not record.family_cnic:
    #             missing_fields.append("Family CNIC")

    #         if missing_fields:
    #             raise ValidationError(_(
    #                 "Please upload the following documents before approval:\n- %s"
    #             ) % ("\n- ".join(missing_fields)))

    #         # If everything is valid
    #         record.state = 'committee_approval'
    def action_complete(self):
        if not self.welfare_line_ids:
            raise ValidationError(_('You must add Welfare Line before completing.'))
        self.state = 'completed'
    
    def action_disburse(self):
        self.state = 'disbursed'
    
    def action_view_previous_disbursement(self):
        """Open the form view of the most recent previous disbursement"""
        self.ensure_one()
        if self.previous_disbursement_id:
            return {
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'welfare',
                'res_id': self.previous_disbursement_id.id,
                'target': 'current',
            }
        return {}
        
    def action_reverse_state(self):
        state_flow = [
            'draft',
            'completed',
            'send_for_inquiry',
            'inquiry',
            'committee_approval',
            'hod_approve',
            'mem_approve',
            'approve',
            'recurring',
            'disbursed',
        ]
        for rec in self:
            if rec.state in ['draft', 'disbursed', 'reject','recurring','approve']:
                continue
            try:
                idx = state_flow.index(rec.state)
                if idx > 0:
                    rec.state = state_flow[idx-1]
            except Exception:
                pass

    # Add this method to your welfare model

    def action_open_full_edit_wizard(self):
        """Open the full-width wizard for editing all fields"""
        self.ensure_one()
        
        # Only allow in committee_approval and hod_approve states
        if self.state not in ['inquiry', 'committee_approval']:
            raise ValidationError(_('This option is only available in Committee Approval and HOD Approval states.'))
        
        return {
            'name': _('Edit All Fields - Full View'),
            'type': 'ir.actions.act_window',
            'res_model': 'welfare.fields.wizard',
            'view_mode': 'form',
            'target': 'new',
            'res_id': False,
            'context': {
                'default_welfare_id': self.id,
                'active_id': self.id,
                'active_model': 'welfare',
            }
        }
        

    def _check_amount_within_hod_limit(self):
        """Check if request amount is within HOD limit"""
        self.ensure_one()
        
        # Get HOD group limit configuration
        hod_group = self.env.ref('bn_welfare.group_welfare_hod', raise_if_not_found=False)
        if not hod_group:
            return True  # No HOD group configured
        
        limit = self.env['welfare.approval.limit'].search([
            ('group_id', '=', hod_group.id),
            ('active', '=', True)
        ], limit=1)
        
        if not limit:
            return True  # No limit configured
        
        # Check amount limit
        if self.loan_request_amount > limit.max_amount_limit:
            return False  # Exceeds HOD limit
        
        # Check product limit
        if limit.allowed_product_master_ids:
            for line in self.welfare_line_ids:
                product_master = self.env['product.master'].search([
                    ('product_id', '=', line.product_id.id)
                ], limit=1)
                if product_master and product_master not in limit.allowed_product_master_ids:
                    return False
        
        return True  # Within HOD limit
    
    def get_required_approval_level(self):
        """Determine required approval level based on limit"""
        self.ensure_one()
        
        if self._check_amount_within_hod_limit():
            return 'hod'  # Within limit - HOD can approve
        else:
            return 'member'  # Exceeds limit - Member must approve  
    
    def can_user_approve_hod(self):
        """Check if current user can approve as HOD"""
        self.ensure_one()
        
        # Check if user has HOD group
        hod_group = self.env.ref('bn_welfare.group_welfare_hod', raise_if_not_found=False)
        if not hod_group or self.env.user not in hod_group.users:
            return False, "User is not in HOD group"
        
        # Check if request is within HOD limit
        if not self._check_amount_within_hod_limit():
            return False, "Request exceeds HOD limit. Only Member can approve."
        
        return True, "HOD can approve"
    
    def can_user_approve_member(self):
        """Check if current user can approve as Member"""
        self.ensure_one()
        
        # Check if user has Member group
        member_group = self.env.ref('bn_welfare.group_welfare_member', raise_if_not_found=False)
        if not member_group or self.env.user not in member_group.users:
            return False, "User is not in Member group"
        
        # Member can always approve (no limit check for member)
        return True, "Member can approve"