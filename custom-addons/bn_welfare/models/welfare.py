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
    ('mem_approve', 'Member Approval'),
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
    
    name = fields.Char('Name', default="NEW")
    cnic_no = fields.Char(related='donee_id.cnic_no', string="CNIC No.", store=True, size=15)
    father_name = fields.Char(related='donee_id.father_name', string="Father Name", store=True)
    father_cnic_no = fields.Char(related='donee_id.father_cnic_no', string="Father CNIC No.", store=True, size=15)
    old_system_id = fields.Char('Old System ID')
    
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
    loan_request_amount = fields.Float('Loan Request Amount')
    
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
    
    show_disburse_button = fields.Boolean(
        compute="_compute_show_disburse_button",
        store=False
    )

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
        
        return super(Welfare, self).create(vals)
    
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
            if app.get('odooId') == self.id:
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

                "odooId": self.id
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
                    "form": {
                        "category": "Individual",  # fix
                        "subcategory": "General Aid",  # fix
                        "donee": self.donee_id.name,
                        "cnic_no": self.cnic_no,
                        "father_name": self.father_name,
                        "date": str(self.date) if self.date else None,
                        "monthly_income": self.monthly_income,
                        "monthly_salary": self.monthly_salary,
                        "loan_request_amount": self.loan_request_amount,
                        "dependent_person": self.dependent_person,
                        "household_member": self.household_member,
                        "residence_type": self.residence_type,
                        "company_name": self.company_name,
                        "company_address": self.company_address,
                        "service_duration": self.service_duration,
                        "bank_account": self.bank_account,
                        "bank_name": self.bank_name,
                        "account_no": self.account_no,
                        "aid_from_other_organization": self.aid_from_other_organization,
                        "have_applied_swit": self.have_applied_swit,
                        "driving_license": self.driving_license,
                        "security_offered": self.security_offered,
                        "other_loan": self.other_loan,
                        "outstanding_amount": self.outstanding_amount,
                        "monthly_household_expense": self.monthly_household_expense,
                        "details_1": self.details_1,
                        "details_2": self.details_2,  
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
        if not self:
            raise UserError("Please select at least one record.")

        invalid = self.filtered(lambda r: r.state != 'completed')
        if invalid:
            raise UserError("Some selected records are not completed and cannot be processed.")

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
                    'portal_last_sync_message': f"Sync started at {fields.Datetime.now()}"
                })
                existing_donee = rec._check_donee_exists_in_portal()
                result = rec._handle_new_application(existing_donee)
                rec._update_sync_status_success(result)
                rec._create_sync_chatter_message(result)
                rec.state = 'send_for_inquiry'
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

        summary = ""
        if success_msgs:
            summary += "<b>Success:</b><br/>" + "<br/>".join(success_msgs) + "<br/>"
        if error_msgs:
            summary += "<b>Errors:</b><br/>" + "<br/>".join(error_msgs)
        if not summary:
            summary = "No records processed."

        return self._show_notification('Send for Inquiry Results', summary, 'info')
    
    def action_move_to_hod(self):
        # if not self.hod_remarks:
        #     raise ValidationError('Please enter HOD Remarks!')
        
        self.state = 'hod_approve'
    
    def action_move_to_member(self):
        # if not self.member_remarks:
        #     raise ValidationError('Please enter Member Remarks!')
        
        self.state = 'mem_approve'
    
    def action_approve(self):
        if self.order_type == 'recurring':
            for line in self.welfare_line_ids:
                if self.env['welfare.recurring.line'].search_count([
                    ('donee_id', '=', self.donee_id.id),
                    ('disbursement_category_id', '=', line.disbursement_category_id.id),
                    ('state', '=', 'draft')
                ]):
                    pass
        self.state = 'approve'

        # Trigger the welfare collection report for printing/giving to the person
        return self.env.ref('bn_welfare.action_report_welfare_collection_document').report_action(self)

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
                
                for i in range(int(line.recurring_duration.split('_')[0])):
                    self.env['welfare.recurring.line'].create({
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
                    })

                    month += 1


        self.state = 'recurring'
        
    def action_committee_approval(self):
        # if not self.committee_remarks:
        #     raise ValidationError(_('Please enter Committee Remarks before approval.'))
        self.state = 'committee_approval'
    def action_complete(self):
        if not self.welfare_line_ids:
            raise ValidationError(_('You must add Welfare Line before completing.'))
        self.state = 'completed'
    
    def action_disburse(self):
        self.state = 'disbursed'
        
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