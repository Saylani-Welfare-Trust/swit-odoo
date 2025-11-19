from odoo import models, fields, _, api
from odoo.exceptions import ValidationError

import logging
from dateutil.relativedelta import relativedelta

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
    ('send_for_inquiry', 'Send for Inquiry'),
    ('inquiry', 'Inquiry Officer'),
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
    ('error', 'Sync Error')
]


class Welfare(models.Model):
    _name = 'welfare'
    _description = "Welfare"

    
    name = fields.Char('Name', default="NEW")
    cnic_no = fields.Char('CNIC No.')
    father_name = fields.Char('Father Name')
    father_cnic_no = fields.Char('Father CNIC No.')
    old_system_id = fields.Char('Old System ID')

    donee_id = fields.Many2one('res.partner', string="Donee")
    employee_id = fields.Many2one('hr.employee', string="Employee")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)

    employee_category_id = fields.Many2one('hr.employee.category', string="Employee Category", default=lambda self: self.env.ref('bn_welfare.inquiry_officer_hr_employee_category', raise_if_not_found=False).id)
    
    date = fields.Date('Date', default=fields.Date.today())
    cnic_expiration_date = fields.Date('CNIC Expiration Date')

    hod_remarks = fields.Text('HOD Remarks')
    member_remarks = fields.Text('Member Remarks')

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
    landlord_cnic_no = fields.Char('CNIC No. of Landlord')
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


    @api.model
    def create(self, vals):
        if vals.get('name', _('NEW')) == _('NEW'):
            vals['name'] = self.env['ir.sequence'].next_by_code('welfare_sequence') or _('New')
        
        return super(Welfare, self).create(vals)
    
    def _check_donee_exists_in_portal(self):
        """Check if donee already exists in portal"""
        try:
            result = self._make_sadqa_api_call(f'{self.env.company.check_donee_endpoint}{self.id}')
            return result.get('data')
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
                message = "❌ Donee not found in portal"
            
            # Check for applications
                applications = self._search_portal_applications()
        
                if applications:
                   message += f" | 📋 {len(applications)} application(s) found"
            
        return self._show_notification('Portal Status Check', message, 'info')
    
    def _find_matching_application(self, applications):
        """Find matching application from portal data"""
        for app in applications:
            # Match by CNIC (most reliable)
            if self.cnic_no and app.get('cnic') == self.cnic_no:
                return app
            # Match by name and WhatsApp
            if (app.get('name') == self.donee_id.name and 
                app.get('whatsapp') == self.donee_id.mobile):
                return app
        return None
    
    def _search_portal_applications(self):
        """Search for matching applications in portal"""
        try:
            result = self._make_sadqa_api_call(self.env.company.search_endpoint)
            applications = result.get('data', [])
            
            if applications:
                # Find matching application based on donee information
                matching_app = self._find_matching_application(applications)
                return matching_app
            return None
            
        except Exception as e:
            _logger.warning(f"No unsynced applications found: {str(e)}")
            return None

    def _mark_application_synced(self, portal_application_id):
        """Mark application as synced in portal"""
        data = {
            "applicationId": portal_application_id,
            "odooId": str(self.id)
        }
        
        result = self._make_sadqa_api_call(self.env.company.mark_application_endpoint, 'POST', data)
        return result.get('data')

    def _handle_existing_application(self, portal_application):
        """Handle existing application found in portal"""
        # Mark application as synced in portal
        synced_application = self._mark_application_synced(portal_application.get('id'))
        
        # Update disbursement record with portal information
        self.write({
            'portal_application_id': portal_application.get('id'),
            'portal_donee_id': synced_application.get('doneeId', ''),
            'is_synced': True,
            'sync_date': fields.Datetime.now(),
            'portal_review_notes': portal_application.get('reviewNotes', '') or portal_application.get('notes', '')
        })
        
        return {
            'action': 'linked_existing',
            'application_id': portal_application.get('id'),
            'message': f"✅ Existing application linked successfully. Application ID: {portal_application.get('id')}",
            'details': f"Donee: {portal_application.get('name')}, CNIC: {portal_application.get('cnic')}"
        }
    
    def _create_donee_in_portal(self):
        """Create donee in Sadqa Jaria portal"""
        data = {
            "name": self.name or '',
            "whatsapp": self.donee_id.mobile or '',
            "cnic": self.cnic_no ,
            "odooId": str(self.id)
        }
        
        result = self._make_sadqa_api_call(self.env.company.create_donee_endpoint, 'POST', data)
        return result.get('data')

    def _handle_new_application(self, existing_donee):
        """Handle creation of new application/donee in portal"""
        donee_data = None
        
        if not existing_donee:
            # Create new donee in portal
            donee_data = self._create_donee_in_portal()
        
        # Update disbursement record with portal information
        update_vals = {
            'portal_donee_id': donee_data.get('id') if donee_data else existing_donee.get('id'),
            'is_synced': True,
            'sync_date': fields.Datetime.now(),
            'portal_application_id': f"CREATED_{fields.Datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }
        
        self.write(update_vals)
        
        action = 'created_donee' if not existing_donee else 'linked_existing_donee'
        message = "✅ New donee created in portal" if not existing_donee else "✅ Existing donee linked in portal"
        
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
                'sticky': True,
            }
        }
    
    def _get_sadqa_api_headers(self):
        """Get API authentication headers"""
        return {
            'x-odoo-auth-key': f'{self.env.company.odoo_auth_key}',
            'Content-Type': 'application/json'
        }

    def action_send_for_inquiry(self):
        self.ensure_one()
        
        # Validate required fields
        if not self.name:
            return self._show_notification('Error', 'Donee name is required for portal sync', 'danger')
        
        if not self.cnic_no and not self.donee_id.mobile:
            return self._show_notification('Error', 'CNIC or WhatsApp / Mobile number is required for portal sync', 'danger')
        
        try:
            # Set status to syncing
            self.write({
                'portal_sync_status': 'syncing',
                'portal_last_sync_message': f"Sync started at {fields.Datetime.now()}"
            })
            
            # Step 1: Check if donee already exists in portal
            existing_donee = self._check_donee_exists_in_portal()
            
            # Step 2: Search for matching applications in portal
            portal_application = self._search_portal_applications()
            
            # Step 3: Handle based on what we found
            if portal_application:
                result = self._handle_existing_application(portal_application)
            else:
                result = self._handle_new_application(existing_donee)
            
            # Step 4: Update sync status and details
            self._update_sync_status_success(result)
            
            # Step 5: Create chatter message
            self._create_sync_chatter_message(result)

            self.state = 'send_for_inquiry'
            
            return self._show_notification('Success', result['message'], 'success')
            
        except Exception as e:
            error_message = f"Portal sync failed: {str(e)}"
            
            # Update error status
            self.write({
                'portal_sync_status': 'error',
                'portal_last_sync_message': error_message,
                'is_synced': False
            })
            
            # Create error chatter message
            self.message_post(body=f"❌ Portal sync failed: {str(e)}")
            
            return self._show_notification('Error', error_message, 'danger')
    
    def action_move_to_hod(self):
        if not self.hod_remarks:
            raise ValidationError('Please enter HOD Remarks!')
        
        self.state = 'hod_approve'
    
    def action_move_to_member(self):
        if not self.member_remarks:
            raise ValidationError('Please enter Member Remarks!')
        
        self.state = 'mem_approve'
    
    def action_approve(self):
        for line in self.disbursement_request_line_ids:
            if line.order_type == 'recurring':
                if self.env['welfare.recurring.line'].search_count([('donee_id', '=', self.donee_id.id), ('disbursement_type_id', '=', line.disbursement_type_id.id), ('state', '=', 'draft')]):
                    raise ValidationError(f"There are recurring disbursement requests in process for {line.disbursement_type_id.name}. Please complete them first.")
    
        self.state = 'approve'

    def action_reject(self):
        self.state = 'reject'

    def action_create_recurring_order(self):
        for line in self.disbursement_request_line_ids:
            if line.order_type != 'recurring':
                raise ValidationError('This request does not belong to recurring order.')
            
            if line.recurring_duration:
                month = 0
                
                for i in range(int(line.recurring_duration.split('_')[0])):
                    self.env['recurring.disbursement.request'].create({
                        'welfare_id': line.welfare_id.id,
                        'collection_date': line.collection_date + relativedelta(months=month),
                        'product_id': line.product_id.id,
                        'currency_id': line.currency_id.id,
                        'analytic_account_id': line.analytic_account_id.id,
                        'disbursement_category_id': line.disbursement_category_id.id,
                        'disbursement_application_type_id': line.disbursement_application_type_id.id,
                        
                        'collection_point': line.collection_point,
                        'amount': line.amount,
                    })

                    month += 1


        self.state = 'recurring'