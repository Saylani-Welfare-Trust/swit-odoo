from odoo import models, fields, _, api
from odoo.exceptions import AccessError, ValidationError, UserError

import requests

import base64
import logging
from dateutil.relativedelta import relativedelta
import json
from odoo.addons.bn_profile_management.models.partner_tag_domain import tag_domain
from urllib.parse import urlparse

_logger = logging.getLogger(__name__)

# Portal search paging: send {limit, cursor}, where cursor is the portal id of the last record of the previous page.
PORTAL_SEARCH_PAGE_LIMIT = 100   # portal accepts 1-100 per page
PORTAL_SEARCH_MAX_PAGES = 200    # safety stop (up to 20,000 applications) so paging can never loop forever

WF = 'bn_welfare.%s'
# Change Inquiry Officer / Reopen Inquiry: the portal's institutional operations, also used for Welfare
WELFARE_INQUIRY_RPC = '/rpc/odoo/institutional/'
# a completed inquiry is reopened before the Final Approval
WELFARE_REOPEN_STATES = ('inquiry', 'committee_approval', 'hod_approve')
# Who acts on a welfare in each status (send on, revert, reject).
STEP_GROUPS = {
    'completed': WF % 'group_bn_welfare_user',
    'send_for_inquiry': WF % 'group_bn_welfare_user',
    'inquiry': WF % 'group_bn_welfare_user',
    'committee_approval': WF % 'group_bn_welfare_committee',
    'hod_approve': WF % 'group_welfare_hod',
    'mem_approve': WF % 'group_welfare_member',
    'approve': WF % 'group_welfare_member',
    'recurring': WF % 'group_welfare_member',
    'return': WF % 'group_welfare_member',
}


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
    ('return', 'Returned'),
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
    _inherit = ['step.activity.mixin', "mail.thread", "mail.activity.mixin"]

    def init(self):
        super().init()
        # the former "consolidated lines" model (never used, removed): its table stays
        # behind when Odoo removes the model on upgrade
        self.env.cr.execute('DROP TABLE IF EXISTS welfare_consolidated_line CASCADE')

    order_type = fields.Selection(order_type_selection, string="Order Type")

    donee_id = fields.Many2one('res.partner', string="Donee", domain=tag_domain('donee', 'welfare', registered=True))
    employee_id = fields.Many2one('hr.employee', string="Employee")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    is_individual = fields.Boolean('Is Individual', default=False) 
    employee_category_id = fields.Many2one('hr.employee.category', string="Employee Category", default=lambda self: self.env.ref('bn_welfare.inquiry_officer_hr_employee_category', raise_if_not_found=False).id)
    employee_category_id_officer = fields.Many2one(
        'hr.employee.category', 
        string='Officer Employee Category', 
        default=lambda self: self.env.ref('bn_welfare.assigned_officer_hr_employee_category', raise_if_not_found=False).id if self.env.ref('bn_welfare.assigned_officer_hr_employee_category', raise_if_not_found=False) else False
    )
    document_image_ids = fields.One2many(
    'welfare.document.image',
    'welfare_id',
    string='Document Images'
)
    name = fields.Char('Name', default="NEW")
    cnic_no = fields.Char(related='donee_id.cnic_no', string="CNIC No.", store=True, size=15)
    father_name = fields.Char(related='donee_id.father_name', string="Father Name", store=True)
    father_cnic_no = fields.Char(related='donee_id.father_cnic_no', string="Father CNIC No.", store=True, size=15)
    old_system_id = fields.Char('Old System ID')
    
    applicantLocationLink = fields.Char('Applicant Location Link') 
    date = fields.Date('Date', default=fields.Date.context_today)
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
    # Store raw URLs (never touched by sanitizer)
    application_form_urls  = fields.Text('Application Form URLs')
    frc_urls               = fields.Text('FRC URLs')
    electricity_bill_urls  = fields.Text('Electricity Bill URLs')
    gas_bill_urls          = fields.Text('Gas Bill URLs')
    family_cnic_urls       = fields.Text('Family CNIC URLs')
    # Computed fields for filtered document images
    # NOTE: One2many fields cannot be computed in Odoo (a comodel inverse name
    # is required and the ORM never calls a compute on x2many), so these were
    # broken no-op declarations. Replaced with the equivalent Many2many fields
    # computed from document_image_ids in _compute_filtered_images below.

    # Computed Html fields for display only — never written by the form

    state = fields.Selection(selection=state_selection, string="State", default='draft')

    welfare_line_ids = fields.One2many('welfare.line', 'welfare_id', string="Welfare Lines")
    welfare_recurring_line_ids = fields.One2many('welfare.recurring.line', 'welfare_id', string='Welfare Recurring Lines')

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
    previous_welfare_source_id = fields.Many2one(
        'welfare', 
        string="Previous Welfare Source",
        help="Used internally to copy document images on save",
        store=True  # Must be stored so it survives the create()
    )

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

    employee_domain = fields.Char('Employee Domain', compute='_compute_employee_domain')
    def _save_portal_images_to_document_model(self):
        field_config = {
            'application_form_urls': 'application_form',
            'frc_urls': 'frc',
            'electricity_bill_urls': 'electricity_bill',
            'gas_bill_urls': 'gas_bill',
            'family_cnic_urls': 'family_cnic',
        }

        for url_field, doc_type in field_config.items():
            raw_urls = getattr(self, url_field, '') or ''
            urls = [u.strip() for u in raw_urls.splitlines() if u.strip()]

            # Delete existing images for this document type
            existing_images = self.document_image_ids.filtered(lambda img: img.document_type == doc_type)
            # the portal sync replaces them (only Welfare Admins delete documents by hand)
            existing_images.sudo().unlink()

            for url in urls:
                try:
                    response = requests.get(url, timeout=15)
                    response.raise_for_status()

                    filename = urlparse(url).path.rsplit('/', 1)[-1] or f"{doc_type}.jpg"

                    # Create using document_image_ids (the main field)
                    self.env['welfare.document.image'].create({
                        'welfare_id': self.id,
                        'document_type': doc_type,
                        'image_data': base64.b64encode(response.content).decode('utf-8'),
                        'image_filename': filename,
                        'source_url': url,
                    })

                    _logger.info("Saved image %s for welfare %s type %s", filename, self.id, doc_type)

                except Exception as e:
                    _logger.error("Failed saving image from %s: %s", url, str(e))
    
    loan_request_amount = fields.Float(
        string='Loan Request Amount',
        default=0.0
    )

    
    loan_tenure_expected = fields.Selection(selection=loan_tenure_selection, string='Loan Tenure Expected')

    security_offered = fields.Char('Security Offered')

    # Guarator Information
    guarantor_line_ids = fields.One2many('microfinance.guarantor', 'welfare_id', string='Guarator Lines')

    # Family Detail
    dependent_person = fields.Integer('No. of Dependents')
    household_member = fields.Integer('Household members')

    family_line_ids = fields.One2many('microfinance.family', 'welfare_id', string='Family Lines')

    # Inquiry Committee Questions Tab
    applicant_occupation = fields.Char('Applicant Occupation / Source of Income', tracking=True)
    residence_ownership = fields.Selection([
        ('owned', 'Owned'),
        ('rented', 'Rented'),
        ('shared', 'Shared'),
    ], string='Residence Ownership', tracking=True)
    total_children = fields.Integer('Total Number of Children', tracking=True)
    boys_count = fields.Integer('Number of Boys', tracking=True)
    
    # Previous Disbursements for same Donee
    
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
    # employee_domain = fields.Char(compute="_compute_employee_domain")
        # Inquiry Committee Questions Fields
    donee_house_status = fields.Char(
        string="Residential Status", 
        help="Does he own the house or live in a rented house?"
    )

    num_of_children = fields.Integer(
        string="Number of Children"
    )

    num_of_sons = fields.Integer(
        string="Number of Sons"
    )

    num_of_daughters = fields.Integer(
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
    @api.depends('donee_id.area', 'employee_category_id')
    def _compute_employee_domain(self):
        for record in self:
            domain = []

            if record.employee_category_id:
                domain.append(('category_ids', 'in', [record.employee_category_id.id]))

            if record.donee_id and record.donee_id.area:
                domain.append(('area', '=', record.donee_id.area.id))

            record.employee_domain = json.dumps(domain)

    def _get_previous_welfare(self):
        """Most recent other application of the same donee that is past draft"""
        self.ensure_one()
        if not self.donee_id:
            return self.browse()
        domain = [('donee_id', '=', self.donee_id.id), ('state', '!=', 'draft')]
        # _origin also excludes the saved record while the form is being edited
        if self._origin.id:
            domain.append(('id', '!=', self._origin.id))
        return self.search(domain, order='date desc, id desc', limit=1)

    @api.depends('donee_id')
    def _compute_previous_disbursement_id(self):
        """Compute the most recent previous disbursement for the same donee"""
        for rec in self:
            rec.previous_disbursement_id = rec._get_previous_welfare()

    @api.onchange('donee_id')
    def _onchange_donee_id_populate_data(self):
        """Auto-populate form data from most recent previous welfare record for existing donee"""
        previous_welfare = self._get_previous_welfare()
        # Reset on every donee change so another donee's documents are never copied
        self.previous_welfare_source_id = previous_welfare

        if previous_welfare:
            self.applicant_occupation = previous_welfare.applicant_occupation
            self.residence_ownership = previous_welfare.residence_ownership
            self.total_children = previous_welfare.total_children
            self.boys_count = previous_welfare.boys_count
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
            self.monthly_income = previous_welfare.monthly_income
            self.outstanding_amount = previous_welfare.outstanding_amount
            self.monthly_household_expense = previous_welfare.monthly_household_expense
            self.bank_account = previous_welfare.bank_account
            self.bank_name = previous_welfare.bank_name
            self.account_no = previous_welfare.account_no
            self.other_loan = previous_welfare.other_loan
            self.institute_name = previous_welfare.institute_name
            self.designation = previous_welfare.designation
            self.company_name = previous_welfare.company_name
            self.company_phone = previous_welfare.company_phone
            self.company_address = previous_welfare.company_address
            self.service_duration = previous_welfare.service_duration
            self.monthly_salary = previous_welfare.monthly_salary
            self.dependent_person = previous_welfare.dependent_person
            self.household_member = previous_welfare.household_member

            if previous_welfare.application_form_urls:
                self.application_form_urls = previous_welfare.application_form_urls
            if previous_welfare.frc_urls:
                self.frc_urls = previous_welfare.frc_urls
            if previous_welfare.electricity_bill_urls:
                self.electricity_bill_urls = previous_welfare.electricity_bill_urls
            if previous_welfare.gas_bill_urls:
                self.gas_bill_urls = previous_welfare.gas_bill_urls
            if previous_welfare.family_cnic_urls:
                self.family_cnic_urls = previous_welfare.family_cnic_urls

            return {
                'warning': {
                    'title': 'Data Auto-Populated',
                    'message': (
                        f'Form has been automatically populated with data from previous application '
                        f'{previous_welfare.name} dated {previous_welfare.date}.\n\n'
                        f'Document images will be copied when you save the record.\n\n'
                        f'Use "View Most Recent Disbursement" to open the previous application.'
                    )
                }
            }
    def _auto_disburse_if_all_lines_delivered(self):
        """Disburse the welfares whose lines are all disbursed. Called on
        records (a line was paid) or on the empty model (all of them)."""
        records = (self or self.search([])).filtered(lambda r: r.state in ('recurring', 'approve'))
        for rec in records:
            if rec.order_type == 'one_time':
                lines = rec.welfare_line_ids.filtered(lambda l: l.state != 'cancel')
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


    def _check_count_values(self, vals):
        """Readable error instead of a crash when text reaches the numeric count fields
        (e.g. from a browser tab opened while they were still text fields)"""
        for fname in ('num_of_children', 'num_of_sons', 'num_of_daughters'):
            value = vals.get(fname)
            if isinstance(value, str) and value.strip() and not value.strip().isdigit():
                raise ValidationError(_(
                    "%s: only numbers are allowed, you can't use alphabets.",
                    self._fields[fname].string,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_count_values(vals)
            if not vals.get('name') or vals.get('name') == 'New':
                seq = self.env['ir.sequence'].sudo().next_by_code('welfare_sequence')
                vals['name'] = seq if seq else _('New')
        records = super().create(vals_list)
        for record in records:
            record._copy_previous_documents()
        return records

    def write(self, vals):
        self._check_count_values(vals)
        res = super().write(vals)
        # Donee changed on an already saved application
        if vals.get('previous_welfare_source_id'):
            self._copy_previous_documents()
        return res

    def _copy_previous_documents(self):
        """Copy the document images of previous_welfare_source_id (set by the donee onchange)"""
        for record in self.filtered('previous_welfare_source_id'):
            # Keep documents already uploaded on this application, only fill the missing types
            existing_types = set(record.document_image_ids.mapped('document_type'))
            for img in record.previous_welfare_source_id.document_image_ids:
                if img.document_type in existing_types:
                    continue
                self.env['welfare.document.image'].sudo().create({
                    'welfare_id':     record.id,
                    'document_type':  img.document_type,
                    'image_data':     img.image_data,
                    'image_filename': img.image_filename,
                    'source_url':     img.source_url,
                })

            # Clear the helper field after copying so it doesn't linger
            record.previous_welfare_source_id = False
    
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
            # Keep the portal's response body: on a 4xx it says which field was rejected
            body = e.response.text[:1000] if e.response is not None else ''
            _logger.error("Sadqa Jaria API Request failed: %s | response: %s", e, body)
            raise Exception(f"Network error: {str(e)}" + (f" | Portal response: {body}" if body else ''))
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
            return result
        except Exception as e:
            _logger.info(f"Donee not found in portal: {str(e)}")
            return None


    def action_check_portal_status(self):
        self.ensure_one()

        if not self.is_synced:
            donee_data = self._check_donee_exists_in_portal()
            if not donee_data:
                self._create_donee_in_portal()

        application = self._search_portal_applications()
        message     = self._apply_portal_application(application)
        return self._show_notification('Portal Status Check', message, 'info')

    def _apply_portal_application(self, application):
        """Pull a completed inquiry from the portal application into this record.

        Shared by the Check Portal Status button and the scheduled action.
        Returns the status message.
        """
        self.ensure_one()
        app_state       = application.get('status') if application else None
        inquiry_reports = application.get('inquiryReports') if application else None

        all_media   = []
        all_remarks = []

        portal_to_html_field = {
            'applicationFormImages': 'application_form_urls',
            'frcImages':             'frc_urls',
            'electricityBillImages': 'electricity_bill_urls',
            'gasBillImages':         'gas_bill_urls',
            'familyCnicImages':      'family_cnic_urls',
        }

        document_aliases = {
            'applicationFormImages': (
                'applicationFormImages', 'applicationFormImage',
                'applicationForm', 'application_form_image',
            ),
            'frcImages': (
                'frcImages', 'frcImage', 'frc', 'frc_image',
            ),
            'electricityBillImages': (
                'electricityBillImages', 'electricityBillImage',
                'electricityBill', 'electricity_bill_image',
            ),
            'gasBillImages': (
                'gasBillImages', 'gasBillImage',
                'gasBill', 'gas_bill_image',
            ),
            'familyCnicImages': (
                'familyCnicImages', 'familyCnicImage',
                'familyCnic', 'family_cnic_image',
            ),
        }

        document_sources = [application]

        if isinstance(inquiry_reports, list):
            for report in inquiry_reports:
                if not isinstance(report, dict):
                    continue
                media   = report.get('media')
                remarks = report.get('remarks')
                if media:
                    for url in media:
                        all_media.append(f'<a href="{url}" target="_blank">View Image</a>')
                if remarks:
                    all_remarks.append(remarks)
                document_sources.append(report)

        if app_state == 'inquiry_complete':
            write_vals = {
                'inquiry_media':       '<br/>'.join(all_media) if all_media else '',
                'portal_review_notes': '\n'.join(all_remarks) if all_remarks else '',
                'state':               'inquiry',
            }

            for portal_field, html_field in portal_to_html_field.items():
                raw_values = []

                for source in document_sources:
                    if not isinstance(source, dict):
                        continue
                    for alias in document_aliases.get(portal_field, (portal_field,)):
                        candidate = source.get(alias)
                        if candidate is None:
                            continue
                        if isinstance(candidate, list):
                            raw_values.extend(candidate)
                        else:
                            raw_values.append(candidate)

                valid_urls = [
                    r for r in raw_values
                    if r and isinstance(r, str) and (
                        r.startswith('http') or r.startswith('/web/content')
                    )
                ]

                if valid_urls:
                    write_vals[html_field] = '\n'.join(valid_urls)
                else:
                    write_vals[html_field] = ''

            # ── 1. Write URLs first ────────────────────────────────
            self.sudo().write(write_vals)

            # ── 2. Then download and save images ──────────────────
            self.sudo()._save_portal_images_to_document_model()

            result  = self._handle_existing_application(application)
            message = f" | 📋 application status: {app_state}"
            message += f" | 📋 {result['message']}"

        else:
            message = " | 📋 No applications found"

        return message

    @api.model
    def _auto_check_portal_status(self):
        """Scheduled action: pull completed inquiries for applications already sent to the portal.

        Pages through the portal search once per run and matches every pending record
        from that single pass, instead of paging through the portal again per record.
        """
        company = self.env.company
        if not company.welfare_url or not company.odoo_auth_key or not company.search_endpoint:
            _logger.warning("Welfare portal status check skipped: portal URL, auth key, or search endpoint is missing.")
            return

        pending = self.search([
            ('state', '=', 'send_for_inquiry'),
            ('is_synced', '=', True),
            ('portal_application_id', '!=', False),
        ])
        if not pending:
            return

        records_by_id = {record.id: record for record in pending}
        found = {}
        for _page, applications in self._iter_portal_application_pages():
            for app in applications:
                if (isinstance(app, dict) and app.get('department') == "welfare"
                        and app.get('odooId') in records_by_id):
                    found.setdefault(app['odooId'], app)
            if len(found) == len(records_by_id):
                break

        _logger.info(
            "Welfare portal status check: %s of %s pending applications found in portal",
            len(found), len(records_by_id),
        )
        for odoo_id, application in found.items():
            record = records_by_id[odoo_id]
            try:
                with self.env.cr.savepoint():
                    message = record._apply_portal_application(application)
                # The portal has been told this application is synced, so commit now:
                # a later failure or cron timeout must not roll this record back.
                self.env.cr.commit()
                _logger.info("Welfare portal status for %s:%s", record.display_name, message)
            except Exception:
                _logger.exception("Could not check Welfare portal status for %s", record.display_name)

    def _find_matching_application(self, applications):
        """Find matching application from portal data"""
        for app in applications:
            if not isinstance(app, dict):
                continue
            # Match by CNIC (most reliable)
            # _logger.info(f"Checking application: {app} and id is system {self.id} portal {app.get('id')}" )
            if app.get('odooId') == self.id and app.get('department') == "welfare":
                return app
        return None
    
    def _search_portal_applications(self):
        """Page through the portal search results until this record's application is found."""
        for page, applications in self._iter_portal_application_pages():
            matching_app = self._find_matching_application(applications)
            if matching_app:
                _logger.info(
                    f"Portal application for odooId {self.id} found on page {page}: "
                    f"id={matching_app.get('id')} status={matching_app.get('status')!r}"
                )
                return matching_app
        _logger.info(f"No portal application found for odooId {self.id}")
        return None

    def _iter_portal_application_pages(self):
        """Yield (page number, applications) for each page of the portal search endpoint.

        Each page is requested with {"limit", "cursor"}, where cursor is the portal id
        ("id", or Mongo "_id") of the last record on the previous page (no cursor for
        the first page). The portal may answer with a plain list or {"data": [...]}.
        Paging stops on a short or empty page, or when the cursor stops advancing;
        callers stop early by breaking out of the loop.
        """
        endpoint = self.env.company.search_endpoint
        cursor = None
        seen_cursors = set()

        for page in range(1, PORTAL_SEARCH_MAX_PAGES + 1):
            payload = {"json": {"limit": PORTAL_SEARCH_PAGE_LIMIT}}
            if cursor is not None:
                payload["json"]["cursor"] = cursor

            try:
                result = self._make_sadqa_api_call(endpoint, 'POST', payload)
            except Exception as e:
                if page > 1:
                    _logger.warning(f"Portal search failed on page {page}: {e}")
                    return
                # The endpoint may not accept a paging body: fall back to the old unpaged call.
                _logger.info(f"Paged portal search failed ({e}); retrying without paging")
                try:
                    result = self._make_sadqa_api_call(endpoint)
                except Exception as fallback_error:
                    _logger.warning(f"No unsynced applications found: {fallback_error}")
                    return

            if isinstance(result, dict):
                applications = result.get('data') or []
            else:
                applications = result or []

            # Cursor for the next page = portal id of the last record that has one.
            next_cursor = next(
                (app.get('id') or app.get('_id') for app in reversed(applications)
                 if isinstance(app, dict) and (app.get('id') or app.get('_id'))),
                None,
            )

            _logger.info(
                f"Portal search page {page} (cursor={cursor!r}): {len(applications)} applications, "
                f"last portal id={next_cursor!r}"
            )

            yield page, applications

            if len(applications) < PORTAL_SEARCH_PAGE_LIMIT:
                return  # short page: this was the last one
            if next_cursor is None or next_cursor in seen_cursors:
                _logger.warning(
                    f"Portal search cannot advance past page {page} "
                    f"(cursor {next_cursor!r} missing or repeated); stopping"
                )
                return
            seen_cursors.add(next_cursor)
            cursor = next_cursor

        _logger.warning(f"Portal search stopped after {PORTAL_SEARCH_MAX_PAGES} pages")

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
        self._mark_application_synced()
        
        
        return {
            'action': 'linked_existing',
            'application_id': portal_application.get('id'),
            'message': f"✅ Existing application linked successfully. Application ID: {portal_application.get('id')}",
            'details': f"Donee: {portal_application.get('name')}"
        }
    
    def _create_donee_in_portal(self):
        """Create donee in Sadqa Jaria portal"""
        donee = self.donee_id

        # Build a readable single-line address from standard partner fields
        address_parts = [
            donee.street,
            donee.street2,
            donee.city,
            donee.state_id.name if donee.state_id else None,
        ]
        full_address = ", ".join(part for part in address_parts if part)

        data = {
                "json":{
                "name": self.donee_id.name or '',
                "whatsapp": self.donee_id.mobile or '',
                "cnic": (
                    self.donee_id.cnic_no.replace("-", "")
                    if self.donee_id.cnic_no else ""
                ),
                "address": full_address,        
                "odooId": self.donee_id.id,
                "area" : self.donee_id.area.name if self.donee_id.area else '',
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
                    "inquiryOfficerEmployeeId": self.employee_id.barcode,
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
        already_on_portal = False
        try:
            portal_application = self.create_portal_application()
        except Exception as e:
            # The portal keys applications by odooId alone, so "already exists" can also mean another
            # record used this id (another department, or an older copy of this database).
            # Link only when it really is this welfare record: listed by the portal as a welfare
            # application, or sent from this record before (reverted to Completed and sent again)
            if f"odooId {self.id} already exists" not in str(e):
                raise
            portal_application = self._search_portal_applications() or {}
            if not portal_application.get('id') and not self.portal_application_id:
                raise Exception(
                    f"The portal already has an application with odooId {self.id}, but it is not this "
                    f"welfare application: this record was never sent before and the portal's welfare list "
                    f"does not have it. Another record used the same id; ask the portal team to check "
                    f"odooId {self.id}.")
            already_on_portal = True
            _logger.info("Welfare application %s already exists on portal; linking it (%s)",
                         self.display_name, portal_application.get('id') or self.portal_application_id)
        portal_application_id = portal_application.get('id') or self.portal_application_id

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
        if already_on_portal:
            message += f" | 📋 Application already on portal, linked{f' (ID: {portal_application_id})' if portal_application_id else ''} "
        else:
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
        
        self._message_log(body=message_body)

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

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        locked = self.filtered(lambda r: r.state not in ('draft', 'reject'))
        if locked:
            raise UserError(_('Only Draft or Rejected welfare applications can be deleted (%s).')
                            % ', '.join(locked.mapped('name')))

    # ------------------------------------------------------------------
    # Workflow checks
    # ------------------------------------------------------------------
    def _check_welfare_state(self, allowed, action):
        labels = dict(state_selection)
        for rec in self:
            if rec.state not in allowed:
                raise UserError(_('"%(action)s" is not possible for %(name)s in status "%(state)s".') % {
                    'action': action, 'name': rec.name, 'state': labels.get(rec.state, rec.state)})

    def _check_welfare_group(self, xmlid, action):
        user = self.env.user
        if self.env.su or user._is_system() or user.has_group(xmlid):
            return
        group = self.env.ref(xmlid, raise_if_not_found=False)
        raise AccessError(_('Only "%(group)s" can do "%(action)s".') % {
            'group': group.name if group else xmlid, 'action': action})

    def _check_step_group(self, action):
        """The group in charge of the current status."""
        for rec in self:
            if rec.state in STEP_GROUPS:
                rec._check_welfare_group(STEP_GROUPS[rec.state], action)

    def action_send_for_inquiry(self):
        """Send for Inquiry - No automatic routing"""
        if not self:
            raise UserError("Please select at least one record.")
        
        invalid = self.filtered(lambda r: r.state != 'completed')
        if invalid:
            raise UserError("Some selected records are not completed and cannot be processed.")
        self._check_welfare_group(WF % 'group_bn_welfare_user', _('Send for Inquiry'))
        
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
                })
                existing_donee = rec._check_donee_exists_in_portal()
                result = rec._handle_new_application(existing_donee)
                rec._update_sync_status_success(result)
                rec._create_sync_chatter_message(result)
                # Move on only once the portal has the application, so a failed send
                # stays in Completed and can simply be sent again (no Revert needed)
                rec.state = 'send_for_inquiry'
                success_msgs.append(f"[{rec.display_name}] {result['message']}")
            except Exception as e:
                error_message = f"[{rec.display_name}] Portal sync failed: {str(e)}"
                rec.write({
                    'portal_sync_status': 'error',
                    'portal_last_sync_message': error_message,
                    'is_synced': False
                })
                rec._message_log(body=f"❌ {error_message}")
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
    def _welfare_officer_call(self, operation, officer):
        """changeInquiryOfficer / reopenInquiry for ``officer`` (by Badge ID); the application is identified by its
        portal ID, Welfare and Sadqa e Jariya Odoo IDs overlap"""
        self.ensure_one()
        if not self.portal_application_id:
            raise UserError(_("%s has no Portal Application ID yet, send it for inquiry first.") % self.name)
        if not officer.active:
            raise UserError(_("Inquiry Officer %s is archived. Reactivate the employee first.") % officer.name)
        employee_id = (officer.barcode or '').strip()
        if not employee_id:
            raise UserError(_("Inquiry Officer %s has no Badge ID, the portal identifies the officer by it.") % officer.name)
        data = {'json': {'applicationId': self.portal_application_id, 'employeeId': employee_id}}
        try:
            return self._make_sadqa_api_call(WELFARE_INQUIRY_RPC + operation, 'POST', data) or {}
        except Exception as e:
            # oRPC error kept by _make_sadqa_api_call: ... | Portal response: {"json": {"code": ..., "message": ...}}
            detail = str(e)
            try:
                error = json.loads(detail.split('Portal response: ', 1)[1])['json']
                detail = f"{error.get('code', '')} {error.get('message', '')}".strip()
            except (IndexError, ValueError, KeyError, TypeError, AttributeError):
                pass
            raise UserError(_("Portal %(operation)s: %(error)s", operation=operation, error=detail)) from e

    def action_open_officer_wizard(self):
        """Change Inquiry Officer / Reopen Inquiry: pick the officer first"""
        self.ensure_one()
        mode = self.env.context.get('officer_wizard_mode', 'reopen')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reopen Inquiry') if mode == 'reopen' else _('Change Inquiry Officer'),
            'res_model': 'welfare.officer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_welfare_id': self.id, 'default_mode': mode,
                        'default_employee_id': self.employee_id.id if mode == 'reopen' else False},
        }

    def action_change_inquiry_officer(self, officer):
        """changeInquiryOfficer: the open inquiry (same report) goes to ``officer``"""
        self.ensure_one()
        self._check_welfare_group(WF % 'group_bn_welfare_user', _('Change Inquiry Officer'))
        self._check_welfare_state(('send_for_inquiry',), _('Change Inquiry Officer'))
        previous = self.employee_id
        self._welfare_officer_call('changeInquiryOfficer', officer)
        self.employee_id = officer
        self._message_log(body=_("👤 Inquiry officer changed on the portal: %s → %s") % (previous.name or '-', officer.name))
        return self._show_notification(_('Change Inquiry Officer'), _('%s can now complete the inquiry.') % officer.name, 'success')

    def action_reopen_inquiry(self, officer):
        """reopenInquiry: a new inquiry report for ``officer``, the welfare goes back to Send for Inquiry
        (Check Portal Status / the scheduled action import it again once completed)"""
        self.ensure_one()
        self._check_welfare_group(WF % 'group_bn_welfare_user', _('Reopen Inquiry'))
        self._check_welfare_state(WELFARE_REOPEN_STATES, _('Reopen Inquiry'))
        self._welfare_officer_call('reopenInquiry', officer)
        self.write({'state': 'send_for_inquiry', 'employee_id': officer.id})
        self._message_log(body=_("🔁 Inquiry reopened on the portal for %s.") % officer.name)
        return self._show_notification(_('Reopen Inquiry'), _('Inquiry reopened, %s can complete a new report.') % officer.name, 'success')

    def action_move_to_hod(self):
        """HOD Approval - Check required fields and documents"""
        self._check_welfare_state(('committee_approval',), _('Move to HOD'))
        self._check_step_group(_('Move to HOD'))
        for record in self:
            # Check for required documents
            missing_fields = []

            if not record.document_image_ids.filtered(lambda i: i.document_type == 'application_form'):
                missing_fields.append("Application Form")
            if not record.document_image_ids.filtered(lambda i: i.document_type == 'frc'):
                missing_fields.append("FRC")
            if not record.document_image_ids.filtered(lambda i: i.document_type == 'electricity_bill'):
                missing_fields.append("Electricity Bill")
            if not record.document_image_ids.filtered(lambda i: i.document_type == 'gas_bill'):
                missing_fields.append("Gas Bill")
            if not record.document_image_ids.filtered(lambda i: i.document_type == 'family_cnic'):
                missing_fields.append("Family CNIC")

            if missing_fields:
                raise ValidationError(_(
                    "Please upload the following documents before HOD approval:\n- %s"
                ) % ("\n- ".join(missing_fields)))

            # Check committee remarks
            if not record.committee_remarks:
                raise ValidationError('Please enter Committee Remarks before moving to HOD approval!')
            
            # Check welfare lines exist
            if not record.welfare_line_ids:
                raise ValidationError('Please add at least one Welfare Line before HOD approval!')

            # Move to HOD approval state
            record.state = 'hod_approve'
            record._add_hod_lines()

            # Add chatter message
            record._message_log(body=_("Application moved to HOD Approval by %s") % record.env.user.name)

    def _add_hod_lines(self):
        """Add an HOD line for every HOD product that has none yet (manual lines of the same product are separate)."""
        hod_products = self.env['product.product'].search([('product_tmpl_id.is_hod', '=', True)])
        cash_category = self.env.ref('bn_welfare.disbursement_category_Cash', raise_if_not_found=False)
        for record in self:
            new_products = hod_products - record.welfare_line_ids.filtered('is_hod').product_id
            if not new_products:
                continue
            self.env['welfare.line'].create([{
                'welfare_id': record.id,
                'product_id': product.id,
                'is_hod': True,
                'disbursement_category_id': cash_category.id if cash_category else False,
                'collection_point': 'branch',
                # The field default is frozen at server start; POS only picks lines due this month
                'collection_date': fields.Date.context_today(record),
            } for product in new_products])

    def action_move_to_member(self):
        """HOD decision: approved directly when within the HOD limit, else
        on to Final Approval."""
        self._check_welfare_state(('hod_approve',), _('Move to Member'))
        self._check_step_group(_('Move to Member'))
        for record in self:
            if not record.hod_remarks:
                raise ValidationError('Please enter HOD Remarks!')
            record.state = 'approve' if record._check_amount_within_hod_limit() else 'mem_approve'
        # HOD lines may all have been disbursed from POS already
        self.filtered(lambda r: r.state == 'approve')._auto_disburse_if_all_lines_delivered()
    def action_approve(self):
        """Final approval logic"""
        self._check_welfare_state(('mem_approve',), _('Approve'))
        self._check_step_group(_('Approve'))
        for record in self:
            if not record.member_remarks:
                raise ValidationError('Please enter Member Remarks!')
            record.state = 'approve'

        # HOD lines may all have been disbursed from POS during Final Approval already
        self._auto_disburse_if_all_lines_delivered()

        # Print report
        return self.env.ref('bn_welfare.action_report_welfare_collection_document').report_action(self)
    

    def action_reject(self):
        self._check_welfare_state(tuple(STEP_GROUPS), _('Reject and Close'))
        self._check_step_group(_('Reject and Close'))
        for rec in self:
            if not rec.rejection_remarks:
                raise ValidationError('Please enter Rejection Remarks before rejection.')
        self.write({'state': 'reject'})

    def action_create_recurring_order(self):
        self.ensure_one()
        self._check_welfare_state(('approve',), _('Create Recurring Orders'))
        self._check_welfare_group(WF % 'group_bn_welfare_user', _('Create Recurring Orders'))
        if self.welfare_recurring_line_ids:
            raise UserError(_('The recurring orders of %s were already created.') % self.name)
        for line in self.welfare_line_ids:
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
                        'payment_type': line.payment_type,
                        'assigned_officer_id': line.assigned_officer_id.id,
                        'amount': line.total_amount,
                        # 'advance_donation_id': line.advance_donation_id.id if line.advance_donation_id.id else None,
                    }
                    
                    self.env['welfare.recurring.line'].create(recurring_line_vals)
                    month += 1

        self.state = 'recurring'

    
    def action_committee_approval(self):
        self._check_welfare_state(('inquiry',), _('Move to Committee Approval'))
        self._check_step_group(_('Move to Committee Approval'))
        self.write({'state': 'committee_approval'})

    def action_complete(self):
        self._check_welfare_state(('draft',), _('Mark as Completed'))
        self._check_welfare_group(WF % 'group_bn_welfare_user', _('Mark as Completed'))
        for rec in self:
            if not rec.welfare_line_ids:
                raise ValidationError(_('You must add Welfare Line before completing.'))
        self.write({'state': 'completed'})

    def action_disburse(self):
        self._check_welfare_state(('approve', 'recurring'), _('Disburse'))
        self._check_step_group(_('Disburse'))
        self.write({'state': 'disbursed'})
    
    def action_view_previous_disbursement(self):
        """Open the form view of the most recent previous disbursement"""
        self.ensure_one()
        if not self.previous_disbursement_id:
            raise UserError(_('No previous application found for this donee.'))
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'welfare',
            'res_id': self.previous_disbursement_id.id,
            'target': 'current',
        }
        
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
        self._check_step_group(_('Revert'))
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
        if self.state not in ['committee_approval', 'hod_approve']:
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

        hod_group = self.env.ref('bn_welfare.group_welfare_hod', raise_if_not_found=False)
        if not hod_group:
            return True

        limit = self.env['welfare.approval.limit'].search([
            ('group_id', '=', hod_group.id),
            ('active', '=', True)
        ], limit=1)

        if not limit:
            return True

        for line in self.welfare_line_ids:
            # Check amount limit
            if line.total_amount > limit.max_amount_limit:
                # self.state = 'mem_approve'
                return False
                # , _(
                #     "Amount (%.2f) on product '%s' exceeds your HOD approval limit (%.2f). "
                #     "This request cannot be approved by HOD."
                # ) % (line.total_amount, line.product_id.name, limit.max_amount_limit)

            # Check product limit only if allowed products are set
            if limit.allowed_product_ids and line.product_id not in limit.allowed_product_ids:
                # self.state = 'mem_approve'

                return False
                # , _(
                #     "Product '%s' is not in the allowed products list for HOD approval. "
                #     "Please contact your administrator."
                # ) % line.product_id.name

        return True


    def action_return_to_pos(self):
        """
        Return all collected Assigned Officer (Marfat) lines for this welfare
        This method is called from the welfare form view button
        """
        self.ensure_one()
        
        # Find all eligible lines
        eligible_lines = self.welfare_line_ids.filtered(
            lambda l: l.payment_type == 'assigned_officer' and l.state == 'pending'
        )
        
        if not eligible_lines:
            raise ValidationError(_(
                "No eligible lines found to return.\n\n"
                "Requirements:\n"
                "• Payment Type: Assigned Officer (Marfat)\n"
                "• Current State: Pending"
            ))
        
        # Process returns
        success_count = 0
        total_amount = 0
        errors = []
        
        for line in eligible_lines:
            try:
                line.action_return_to_pos()
                success_count += 1
                total_amount += line.total_amount
            except Exception as e:
                errors.append(f"{line.product_id.name}: {str(e)}")
        
        # Show results
        if errors:
            error_message = "\n".join(errors)
            raise ValidationError(_(
                "Partial return completed.\n\n"
                "Successfully returned: %s line(s) totaling %s\n\n"
                "Errors:\n%s"
            ) % (success_count, total_amount, error_message))
        
        # Show success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Return Successful'),
                'message': _('Successfully returned %s line(s) totaling %s') % (success_count, total_amount),
                'type': 'success',
                'sticky': False,
            }
        }
    
    
    def action_print_info(self):
        self.ensure_one()
        if not self.donee_id:
            raise UserError(_("No Donee is set on this Welfare record."))
        if not self.donee_id.exists():
            raise UserError(_("The linked Donee (partner) record does not exist or has been deleted."))
        
        # Use sudo to bypass potential access restrictions on the partner (e.g., inactive record)
        partner = self.donee_id.sudo()
        
        # Pass the welfare record ID in `data` (the action context is dropped for PDF downloads)
        # so the report can show welfare‑specific data
        return self.env.ref(
            'bn_profile_management.action_profile_management_report'
        ).report_action(partner, data={'welfare_id': self.id, 'partner_ids': partner.ids})