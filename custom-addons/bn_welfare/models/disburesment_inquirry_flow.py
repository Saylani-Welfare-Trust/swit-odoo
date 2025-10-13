from odoo import fields, models, api, exceptions, _

from dateutil.relativedelta import relativedelta

import requests
import json
import logging
_logger = logging.getLogger(__name__)
from odoo import models, fields, api
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class DisbursementRequest(models.Model):
    _inherit = 'disbursement.request'

    portal_application_id = fields.Char(string='Portal Application ID', readonly=True)
    portal_donee_id = fields.Char(string='Portal Donee ID', readonly=True)
    is_synced = fields.Boolean(string='Synced to Portal', default=False)
    sync_date = fields.Datetime(string='Last Sync Date')

      
    # Additional fields for portal integration
    portal_sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('syncing', 'Syncing'),
        ('synced', 'Synced'),
        ('error', 'Sync Error')
    ], string='Portal Sync Status', default='not_synced', readonly=True)
    
    portal_review_notes = fields.Text(string='Portal Review Notes', readonly=True)
    portal_last_sync_message = fields.Char(string='Last Sync Message', readonly=True)
    
    # Donee information fields (assuming these exist or adding them)

    donee_whatsapp = fields.Char(string='WhatsApp Number',)

    
    def _get_sadqa_api_headers(self):
        """Get API authentication headers"""
        return {
            'x-odoo-auth-key': 'df020b0ebc1ef6ce64e32dfaf10fbc65',
            'Content-Type': 'application/json'
        }
    
    def _make_sadqa_api_call(self, endpoint, method='GET', data=None):
        """Make API call to Sadqa Jaria portal"""
        base_url = 'https://backend.switsjmm.com'
        url = f"{base_url}{endpoint}"
        headers = self._get_sadqa_api_headers()


        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            result = response.json()
            # raise exceptions.ValidationError(str("result",result))

            
            if not result.get('success'):
                error_msg = result.get('error', 'Unknown error occurred')
                raise Exception(f"Portal API Error: {error_msg}")
            # raise exceptions.ValidationError(str("result",result))
                
            return result
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"Sadqa Jaria API Request failed: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            _logger.error(f"Sadqa Jaria API Processing failed: {str(e)}")
            raise e
        
    def get_unsynced_applications(self):
        """Get unsynced applications from portal"""
        return self._make_api_call('/api/odoo/un-synced-organization-applications')
    
    def mark_application_synced(self, application_id, odoo_id):
        """Mark application as synced in portal"""
        data = {
            "applicationId": application_id,
            "odooId": odoo_id
        }
        return self._make_api_call('/api/odoo/mark-application-synced', 'POST', data)
    
    def create_donee(self, name, whatsapp, cnic, odoo_id):
        """Create donee in portal"""
        data = {
            "name": name,
            "whatsapp": whatsapp,
            "cnic": cnic,
            "odooId": odoo_id
        }
        return self._make_api_call('/api/odoo/done', 'POST', data)
    
    def check_donee_exists(self, odoo_id):
        """Check if donee exists in portal"""
        return self._make_api_call(f'/api/odoo/donee/{odoo_id}')
    

    def _search_portal_applications(self):
        """Search for matching applications in portal"""
        try:
            result = self._make_sadqa_api_call('/api/odoo/un-synced-organization-applications')
            applications = result.get('data', [])
            
            if applications:
                # Find matching application based on donee information
                matching_app = self._find_matching_application(applications)
                return matching_app
            return None
            
        except Exception as e:
            _logger.warning(f"No unsynced applications found: {str(e)}")
            return None
    
    def _find_matching_application(self, applications):
        """Find matching application from portal data"""
        for app in applications:
            # Match by CNIC (most reliable)
            if self.donee_cnic and app.get('cnic') == self.donee_cnic:
                return app
            # Match by name and WhatsApp
            if (app.get('name') == self.donee_name and 
                app.get('whatsapp') == self.donee_whatsapp):
                return app
        return None
    
    def _check_donee_exists_in_portal(self):
        """Check if donee already exists in portal"""
        try:
            result = self._make_sadqa_api_call(f'/api/odoo/donee/{self.id}')
            return result.get('data')
        except Exception as e:
            _logger.info(f"Donee not found in portal: {str(e)}")
            return None
    
    def _create_donee_in_portal(self):
        """Create donee in Sadqa Jaria portal"""
        data = {
            "name": self.name or '',
            "whatsapp": self.donee_whatsapp or '',
            "cnic": self.cnic_no ,
            "odooId": str(self.id)
        }
        
        result = self._make_sadqa_api_call('/api/odoo/done', 'POST', data)
        return result.get('data')
    
    def _mark_application_synced(self, portal_application_id):
        """Mark application as synced in portal"""
        data = {
            "applicationId": portal_application_id,
            "odooId": str(self.id)
        }
        
        result = self._make_sadqa_api_call('/api/odoo/mark-application-synced', 'POST', data)
        return result.get('data')
    

    def action_sync_with_sadqa_portal(self):
        """Main button action: Search, Create, and Sync with Sadqa Jaria Portal"""
        self.ensure_one()
        
        # Validate required fields
        if not self.name:
            return self._show_notification('Error', 'Donee name is required for portal sync', 'danger')
        
        if not self.cnic_no and not self.donee_whatsapp:
            return self._show_notification('Error', 'CNIC or WhatsApp number is required for portal sync', 'danger')
        
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
            
            return self._show_notification('Success', result['message'], 'success')
            
        except Exception as e:
            error_message = f"Portal sync failed: {str(e)}"
            _logger.error(error_message)
            
            # Update error status
            self.write({
                'portal_sync_status': 'error',
                'portal_last_sync_message': error_message,
                'is_synced': False
            })
            
            # Create error chatter message
            self.message_post(body=f"❌ Portal sync failed: {str(e)}")
            
            return self._show_notification('Error', error_message, 'danger')
    
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
            
        # except Exception as e:
            # return self._show_notification('Status Check Error', str(e), 'danger')
    
    def action_force_resync(self):
        """Force resync with portal"""
        self.ensure_one()
        
        # Reset sync status
        self.write({
            'portal_sync_status': 'not_synced',
            'is_synced': False,
            'portal_application_id': False,
            'portal_donee_id': False,
            'portal_last_sync_message': 'Reset for re-sync'
        })
        
        self.message_post(body="🔄 Manual re-sync initiated")
        
        return self.action_sync_with_sadqa_portal()
    
    def _cron_sync_pending_requests(self):
        """Automated sync for pending requests (call via cron)"""
        domain = [
            ('portal_sync_status', 'in', ['not_synced', 'error']),
            ('state', '=', 'inquiry'),  # Only sync approved requests
            ('donee_name', '!=', False)
        ]
        
        pending_requests = self.search(domain, limit=50)  # Limit to avoid timeout
        
        for request in pending_requests:
            try:
                _logger.info(f"Auto-syncing disbursement request: {request.name}")
                request.action_sync_with_sadqa_portal()
            except Exception as e:
                _logger.error(f"Auto-sync failed for {request.name}: {str(e)}")
                continue

  

    
   

# from odoo import fields, models, api, exceptions, _
# from dateutil.relativedelta import relativedelta
# import requests
# import json
# import logging
# from datetime import datetime

# _logger = logging.getLogger(__name__)

# class DisbursementRequest(models.Model):
#     _inherit = 'disbursement.request'

#     portal_application_id = fields.Char(string='Portal Application ID', readonly=True)
#     portal_donee_id = fields.Char(string='Portal Donee ID', readonly=True)
#     is_synced = fields.Boolean(string='Synced to Portal', default=False)
#     sync_date = fields.Datetime(string='Last Sync Date')
    
#     # Additional fields for portal integration
#     portal_sync_status = fields.Selection([
#         ('not_synced', 'Not Synced'),
#         ('syncing', 'Syncing'),
#         ('synced', 'Synced'),
#         ('error', 'Sync Error')
#     ], string='Portal Sync Status', default='not_synced', readonly=True)
    
#     portal_review_notes = fields.Text(string='Portal Review Notes', readonly=True)
#     portal_last_sync_message = fields.Char(string='Last Sync Message', readonly=True)
    
#     # Donee information fields
#     donee_whatsapp = fields.Char(string='WhatsApp Number')

#     # New fields for organization applications
#     application_category = fields.Selection([
#         ('madrasa', 'Madrasa'),
#         ('organization', 'Organization'),
#         ('individual', 'Individual')
#     ], string='Application Category')
    
#     application_subcategory = fields.Char(string='Application Subcategory')
#     application_province = fields.Char(string='Province')
#     application_token = fields.Char(string='Application Token')
#     application_submitted_date = fields.Datetime(string='Submitted Date')

#     def _get_sadqa_api_headers(self):
#         """Get API authentication headers"""
#         return {
#             'x-odoo-auth-key': 'df020b0ebc1ef6ce64e32dfaf10fbc65',
#             'Content-Type': 'application/json'
#         }
    
#     def _make_sadqa_api_call(self, endpoint, method='GET', data=None):
#         """Make API call to Sadqa Jaria portal"""
#         base_url = 'https://backend.switsjmm.com'
#         url = f"{base_url}{endpoint}"
#         headers = self._get_sadqa_api_headers()

#         try:
#             if method.upper() == 'GET':
#                 response = requests.get(url, headers=headers, timeout=30)
#             elif method.upper() == 'POST':
#                 response = requests.post(url, headers=headers, json=data, timeout=30)
#             else:
#                 raise ValueError(f"Unsupported HTTP method: {method}")
            
#             response.raise_for_status()
#             result = response.json()
            
#             if not result.get('success'):
#                 error_msg = result.get('error', 'Unknown error occurred')
#                 raise Exception(f"Portal API Error: {error_msg}")
                
#             return result
            
#         except requests.exceptions.RequestException as e:
#             _logger.error(f"Sadqa Jaria API Request failed: {str(e)}")
#             raise Exception(f"Network error: {str(e)}")
#         except Exception as e:
#             _logger.error(f"Sadqa Jaria API Processing failed: {str(e)}")
#             raise e

#     # NEW METHODS FOR FETCHING AND CREATING RECORDS FROM API
#     def action_fetch_unsynced_applications(self):
#         """Button action to fetch unsynced applications from portal"""
#         try:
#             result = self._make_sadqa_api_call('/api/odoo/un-synced-organization-applications')
            
#             if result.get('success') and result.get('data'):
#                 applications = result.get('data', [])
#                 created_count = 0
#                 updated_count = 0
                
#                 for app_data in applications:
#                     # Check if application already exists
#                     existing_record = self.search([
#                         ('portal_application_id', '=', app_data.get('_id'))
#                     ], limit=1)
                    
#                     if existing_record:
#                         # Update existing record
#                         existing_record._update_from_portal_data(app_data)
#                         updated_count += 1
#                     else:
#                         # Create new record
#                         self._create_from_portal_data(app_data)
#                         created_count += 1
                
#                 message = f"✅ Sync completed: {created_count} new records created, {updated_count} records updated"
#                 return self._show_notification('Success', message, 'success')
#             else:
#                 return self._show_notification('Info', 'No unsynced applications found', 'info')
                
#         except Exception as e:
#             error_message = f"Failed to fetch applications: {str(e)}"
#             _logger.error(error_message)
#             return self._show_notification('Error', error_message, 'danger')

#     def _create_from_portal_data(self, app_data):
#         """Create a new disbursement request from portal data"""
#         try:
#             form_data = app_data.get('form', {})
#             applicant_info = form_data.get('applicantInformation', {})
#             madrasa_info = form_data.get('madrasaInfo', {})
#             account_details = form_data.get('accountDetails', {})
#             submitted_by = app_data.get('submittedBy', {})
            
#             # Map portal status to Odoo status
#             status_mapping = {
#                 'hod-review': 'to_approve',
#                 'trustee-review': 'mem_approve',
#                 'approved': 'approved',
#                 'rejected': 'reject',
#                 'draft': 'draft',
#                 'inquiry': 'inquiry'
#             }
            
#             # Create or find partner
#             partner_id = self._get_or_create_partner_from_app(app_data)
            
#             # Prepare values for new record
#             values = {
#                 'portal_application_id': app_data.get('_id'),
#                 'application_token': app_data.get('token'),
#                 'application_category': app_data.get('category'),
#                 'application_subcategory': app_data.get('subCategory'),
#                 'application_province': app_data.get('province'),
#                 'application_submitted_date': self._parse_datetime(app_data.get('createdAt')),
                
#                 'donee_id': partner_id.id if partner_id else False,
#                 'name': applicant_info.get('name', submitted_by.get('fullname', '')),
#                 'cnic_no': submitted_by.get('cnic', ''),
#                 'donee_whatsapp': submitted_by.get('whatsapp', applicant_info.get('phoneNumber', '')),
                
#                 'state': status_mapping.get(app_data.get('status', 'draft'), 'draft'),
#                 'disbursement_date': fields.Date.today(),
                
#                 # Organization details
#                 'company_name': madrasa_info.get('madarsaName', ''),
#                 'designation': applicant_info.get('designation', ''),
#                 'company_address': madrasa_info.get('address', ''),
#                 'company_phone_no': applicant_info.get('phoneNumber', ''),
                
#                 # Financial information
#                 'monthly_salary': float(form_data.get('fundInfo', {}).get('monthlyFundCollection', 0)) or 0,
#                 'bank_name': account_details.get('accountType', ''),
#                 'account_no': account_details.get('accountNumber', ''),
#                 'institute_name': madrasa_info.get('madarsaName', ''),
                
#                 # Additional info
#                 'details_1': f"Category: {app_data.get('category', '')} - Subcategory: {app_data.get('subCategory', '')}",
#                 'details_2': f"Province: {app_data.get('province', '')} - Token: {app_data.get('token', '')}",
                
#                 # Portal sync info
#                 'portal_sync_status': 'synced',
#                 'is_synced': True,
#                 'sync_date': fields.Datetime.now(),
#                 'portal_last_sync_message': f"Created from portal on {fields.Datetime.now()}",
#             }
            
#             # Create the disbursement request
#             disbursement_record = self.create(values)
            
#             # Create related records
#             disbursement_record._create_related_records_from_app(app_data)
            
#             # Mark as synced in portal
#             disbursement_record._mark_application_synced_in_portal(app_data.get('_id'))
            
#             _logger.info(f"Created disbursement record from portal: {disbursement_record.name}")
#             return disbursement_record
            
#         except Exception as e:
#             _logger.error(f"Error creating record from portal data: {str(e)}")
#             raise

#     def _update_from_portal_data(self, app_data):
#         """Update existing record with latest portal data"""
#         try:
#             form_data = app_data.get('form', {})
#             applicant_info = form_data.get('applicantInformation', {})
            
#             # Map portal status to Odoo status
#             status_mapping = {
#                 'hod-review': 'to_approve',
#                 'trustee-review': 'mem_approve',
#                 'approved': 'approved',
#                 'rejected': 'reject',
#                 'draft': 'draft',
#                 'inquiry': 'inquiry'
#             }
            
#             update_vals = {
#                 'application_token': app_data.get('token'),
#                 'application_category': app_data.get('category'),
#                 'application_subcategory': app_data.get('subCategory'),
#                 'application_province': app_data.get('province'),
#                 'state': status_mapping.get(app_data.get('status', self.state), self.state),
#                 'name': applicant_info.get('name', self.name),
#                 'portal_last_sync_message': f"Updated from portal on {fields.Datetime.now()}",
#                 'sync_date': fields.Datetime.now(),
#             }
            
#             self.write(update_vals)
            
#             # Update related records if needed
#             self._update_related_records_from_app(app_data)
            
#             _logger.info(f"Updated disbursement record from portal: {self.name}")
            
#         except Exception as e:
#             _logger.error(f"Error updating record from portal data: {str(e)}")
#             raise

#     def _get_or_create_partner_from_app(self, app_data):
#         """Get or create partner record from application data"""
#         try:
#             submitted_by = app_data.get('submittedBy', {})
#             applicant_info = app_data.get('form', {}).get('applicantInformation', {})
            
#             cnic = submitted_by.get('cnic', '')
#             if cnic:
#                 partner = self.env['res.partner'].search([('cnic_no', '=', cnic)], limit=1)
#                 if partner:
#                     return partner
            
#             # Create new partner
#             partner_values = {
#                 'name': applicant_info.get('name', submitted_by.get('fullname', 'Unknown')),
#                 'cnic_no': cnic,
#                 'phone': submitted_by.get('whatsapp', applicant_info.get('phoneNumber', '')),
#                 'email': submitted_by.get('email', ''),
#                 'street': applicant_info.get('applicantLocationLink', ''),
#                 'is_company': True,  # Since these are organizations
#             }
            
#             return self.env['res.partner'].create(partner_values)
            
#         except Exception as e:
#             _logger.error(f"Error creating partner from app: {str(e)}")
#             return None

#     def _create_related_records_from_app(self, app_data):
#         """Create related records (committee members, teachers, etc.)"""
#         try:
#             form_data = app_data.get('form', {})
            
#             # Create committee members as family information
#             committee_members = form_data.get('committeeMembers', [])
#             for member in committee_members:
#                 self.env['family.information'].create({
#                     'disbursement_request_id': self.id,
#                     'name': member.get('committeeMemberName', ''),
#                     'cnic_no': member.get('cnic', ''),
#                     'phone_no': member.get('phonenumber', ''),
#                     'relation_with_applicant': 'committee_member',
#                     'designation': member.get('designation', ''),
#                 })
            
#             # Create teachers as family information
#             teachers = form_data.get('teachers', [])
#             for teacher in teachers:
#                 self.env['family.information'].create({
#                     'disbursement_request_id': self.id,
#                     'name': teacher.get('teacherName', ''),
#                     'cnic_no': teacher.get('cnic', ''),
#                     'phone_no': teacher.get('phonenumber', ''),
#                     'relation_with_applicant': 'teacher',
#                     'designation': teacher.get('designation', ''),
#                 })
            
#             # Create inquiry reports as notes
#             inquiry_reports = app_data.get('inquiryReports', [])
#             for report in inquiry_reports:
#                 officer_name = report.get('officerId', {}).get('fullname', 'Unknown Officer')
#                 content = report.get('content', '')
#                 status = report.get('status', '')
                
#                 self.message_post(
#                     body=f"<b>Portal Inquiry Report</b><br/>"
#                          f"Officer: {officer_name}<br/>"
#                          f"Status: {status}<br/>"
#                          f"Content: {content}<br/>"
#                          f"Date: {self._parse_datetime(report.get('createdAt'))}",
#                     subject=f"Inquiry Report - {status}"
#                 )
            
#             _logger.info(f"Created related records for {self.name}")
            
#         except Exception as e:
#             _logger.error(f"Error creating related records: {str(e)}")

#     def _update_related_records_from_app(self, app_data):
#         """Update related records if needed"""
#         # For now, we'll just add new inquiry reports as notes
#         try:
#             inquiry_reports = app_data.get('inquiryReports', [])
#             for report in inquiry_reports:
#                 # Check if this report already exists as a note
#                 existing_notes = self.message_ids.filtered(
#                     lambda m: f"Inquiry Report - {report.get('status')}" in m.subject
#                 )
                
#                 if not existing_notes:
#                     officer_name = report.get('officerId', {}).get('fullname', 'Unknown Officer')
#                     content = report.get('content', '')
#                     status = report.get('status', '')
                    
#                     self.message_post(
#                         body=f"<b>Portal Inquiry Report (Update)</b><br/>"
#                              f"Officer: {officer_name}<br/>"
#                              f"Status: {status}<br/>"
#                              f"Content: {content}",
#                         subject=f"Inquiry Report - {status}"
#                     )
                    
#         except Exception as e:
#             _logger.error(f"Error updating related records: {str(e)}")

#     def _mark_application_synced_in_portal(self, application_id):
#         """Mark application as synced in portal"""
#         try:
#             data = {
#                 "applicationId": application_id,
#                 "odooId": str(self.id)
#             }
#             self._make_sadqa_api_call('/api/odoo/mark-application-synced', 'POST', data)
#             _logger.info(f"Marked application {application_id} as synced in portal")
#         except Exception as e:
#             _logger.warning(f"Could not mark application as synced in portal: {str(e)}")

#     def _parse_datetime(self, datetime_str):
#         """Parse datetime string from portal format"""
#         if not datetime_str:
#             return False
#         try:
#             return fields.Datetime.to_string(
#                 datetime.strptime(datetime_str.replace('Z', ''), '%Y-%m-%dT%H:%M:%S.%f')
#             )
#         except:
#             try:
#                 return fields.Datetime.to_string(
#                     datetime.strptime(datetime_str.replace('Z', ''), '%Y-%m-%dT%H:%M:%S')
#                 )
#             except:
#                 return False

#     # KEEP YOUR EXISTING METHODS (with minor adjustments if needed)
#     def _search_portal_applications(self):
#         """Search for matching applications in portal"""
#         try:
#             result = self._make_sadqa_api_call('/api/odoo/un-synced-organization-applications')
#             applications = result.get('data', [])
            
#             if applications:
#                 # Find matching application based on donee information
#                 matching_app = self._find_matching_application(applications)
#                 return matching_app
#             return None
            
#         except Exception as e:
#             _logger.warning(f"No unsynced applications found: {str(e)}")
#             return None

#     def _find_matching_application(self, applications):
#         """Find matching application from portal data"""
#         for app in applications:
#             # Match by CNIC (most reliable)
#             if self.cnic_no and app.get('submittedBy', {}).get('cnic') == self.cnic_no:
#                 return app
#             # Match by name
#             app_name = app.get('form', {}).get('applicantInformation', {}).get('name', '')
#             if app_name and app_name == self.name:
#                 return app
#         return None

#     def _check_donee_exists_in_portal(self):
#         """Check if donee already exists in portal"""
#         try:
#             result = self._make_sadqa_api_call(f'/api/odoo/donee/{self.id}')
#             return result.get('data')
#         except Exception as e:
#             _logger.info(f"Donee not found in portal: {str(e)}")
#             return None

#     def _create_donee_in_portal(self):
#         """Create donee in Sadqa Jaria portal"""
#         data = {
#             "name": self.name or '',
#             "whatsapp": self.donee_whatsapp or '',
#             "cnic": self.cnic_no or '',
#             "odooId": str(self.id)
#         }
        
#         result = self._make_sadqa_api_call('/api/odoo/done', 'POST', data)
#         return result.get('data')

#     def _mark_application_synced(self, portal_application_id):
#         """Mark application as synced in portal"""
#         data = {
#             "applicationId": portal_application_id,
#             "odooId": str(self.id)
#         }
        
#         result = self._make_sadqa_api_call('/api/odoo/mark-application-synced', 'POST', data)
#         return result.get('data')

#     def action_sync_with_sadqa_portal(self):
#         """Main button action: Search, Create, and Sync with Sadqa Jaria Portal"""
#         # Your existing implementation remains the same
#         self.ensure_one()
        
#         # Validate required fields
#         if not self.name:
#             return self._show_notification('Error', 'Donee name is required for portal sync', 'danger')
        
#         if not self.cnic_no and not self.donee_whatsapp:
#             return self._show_notification('Error', 'CNIC or WhatsApp number is required for portal sync', 'danger')
        
#         try:
#             # Set status to syncing
#             self.write({
#                 'portal_sync_status': 'syncing',
#                 'portal_last_sync_message': f"Sync started at {fields.Datetime.now()}"
#             })
            
#             # Step 1: Check if donee already exists in portal
#             existing_donee = self._check_donee_exists_in_portal()
            
#             # Step 2: Search for matching applications in portal
#             portal_application = self._search_portal_applications()
            
#             # Step 3: Handle based on what we found
#             if portal_application:
#                 result = self._handle_existing_application(portal_application)
#             else:
#                 result = self._handle_new_application(existing_donee)
            
#             # Step 4: Update sync status and details
#             self._update_sync_status_success(result)
            
#             # Step 5: Create chatter message
#             self._create_sync_chatter_message(result)
            
#             return self._show_notification('Success', result['message'], 'success')
            
#         except Exception as e:
#             error_message = f"Portal sync failed: {str(e)}"
#             _logger.error(error_message)
            
#             # Update error status
#             self.write({
#                 'portal_sync_status': 'error',
#                 'portal_last_sync_message': error_message,
#                 'is_synced': False
#             })
            
#             # Create error chatter message
#             self.message_post(body=f"❌ Portal sync failed: {str(e)}")
            
#             return self._show_notification('Error', error_message, 'danger')

#     def _handle_existing_application(self, portal_application):
#         """Handle existing application found in portal"""
#         # Mark application as synced in portal
#         synced_application = self._mark_application_synced(portal_application.get('_id'))
        
#         # Update disbursement record with portal information
#         self.write({
#             'portal_application_id': portal_application.get('_id'),
#             'portal_donee_id': synced_application.get('doneeId', ''),
#             'is_synced': True,
#             'sync_date': fields.Datetime.now(),
#             'portal_review_notes': portal_application.get('reviewNotes', '') or portal_application.get('notes', '')
#         })
        
#         return {
#             'action': 'linked_existing',
#             'application_id': portal_application.get('_id'),
#             'message': f"✅ Existing application linked successfully. Application ID: {portal_application.get('_id')}",
#             'details': f"Donee: {portal_application.get('form', {}).get('applicantInformation', {}).get('name', '')}"
#         }

#     def _handle_new_application(self, existing_donee):
#         """Handle creation of new application/donee in portal"""
#         donee_data = None
        
#         if not existing_donee:
#             # Create new donee in portal
#             donee_data = self._create_donee_in_portal()
        
#         # Update disbursement record with portal information
#         update_vals = {
#             'portal_donee_id': donee_data.get('id') if donee_data else existing_donee.get('id'),
#             'is_synced': True,
#             'sync_date': fields.Datetime.now(),
#             'portal_application_id': f"CREATED_{fields.Datetime.now().strftime('%Y%m%d_%H%M%S')}"
#         }
        
#         self.write(update_vals)
        
#         action = 'created_donee' if not existing_donee else 'linked_existing_donee'
#         message = "✅ New donee created in portal" if not existing_donee else "✅ Existing donee linked in portal"
        
#         return {
#             'action': action,
#             'donee_id': donee_data.get('id') if donee_data else existing_donee.get('id'),
#             'message': message,
#             'details': f"Donee ID: {donee_data.get('id') if donee_data else existing_donee.get('id')}"
#         }

#     def _update_sync_status_success(self, result):
#         """Update successful sync status"""
#         self.write({
#             'portal_sync_status': 'synced',
#             'portal_last_sync_message': f"Success: {result['message']} at {fields.Datetime.now()}"
#         })

#     def _create_sync_chatter_message(self, result):
#         """Create chatter message for sync activity"""
#         message_body = f"""
#         <b>🔄 Sadqa Jaria Portal Sync Completed</b>
#         <br/>
#         <b>Action:</b> {result['action'].replace('_', ' ').title()}
#         <br/>
#         <b>Status:</b> ✅ Success
#         <br/>
#         <b>Message:</b> {result['message']}
#         <br/>
#         <b>Details:</b> {result.get('details', 'N/A')}
#         <br/>
#         <b>Sync Date:</b> {fields.Datetime.now()}
#         """
        
#         self.message_post(body=message_body)

#     def _show_notification(self, title, message, type='info'):
#         """Show notification to user"""
#         return {
#             'type': 'ir.actions.client',
#             'tag': 'display_notification',
#             'params': {
#                 'title': title,
#                 'message': message,
#                 'type': type,
#                 'sticky': True,
#             }
#         }

#     def action_check_portal_status(self):
#         """Check current status in portal"""
#         self.ensure_one()
        
#         try:
#             # Check if donee exists
#             donee_data = self._check_donee_exists_in_portal()
            
#             if donee_data:
#                 message = f"✅ Donee exists in portal. Name: {donee_data.get('name')}"
#             else:
#                 message = "❌ Donee not found in portal"
            
#             # Check for applications
#             applications = self._search_portal_applications()
        
#             if applications:
#                 message += f" | 📋 {len(applications)} application(s) found"
            
#             return self._show_notification('Portal Status Check', message, 'info')
            
#         except Exception as e:
#             return self._show_notification('Status Check Error', str(e), 'danger')

#     def action_force_resync(self):
#         """Force resync with portal"""
#         self.ensure_one()
        
#         # Reset sync status
#         self.write({
#             'portal_sync_status': 'not_synced',
#             'is_synced': False,
#             'portal_application_id': False,
#             'portal_donee_id': False,
#             'portal_last_sync_message': 'Reset for re-sync'
#         })
        
#         self.message_post(body="🔄 Manual re-sync initiated")
        
#         return self.action_sync_with_sadqa_portal()

#     def _cron_sync_pending_requests(self):
#         """Automated sync for pending requests (call via cron)"""
#         domain = [
#             ('portal_sync_status', 'in', ['not_synced', 'error']),
#             ('state', '=', 'inquiry'),  # Only sync approved requests
#             ('name', '!=', False)
#         ]
        
#         pending_requests = self.search(domain, limit=50)  # Limit to avoid timeout
        
#         for request in pending_requests:
#             try:
#                 _logger.info(f"Auto-syncing disbursement request: {request.name}")
#                 request.action_sync_with_sadqa_portal()
#             except Exception as e:
#                 _logger.error(f"Auto-sync failed for {request.name}: {str(e)}")
#                 continue

#     # NEW CRON METHOD FOR FETCHING UNSYNCED APPLICATIONS
#     def _cron_fetch_unsynced_applications(self):
#         """Automated cron to fetch unsynced applications from portal"""
#         try:
#             _logger.info("Starting automated fetch of unsynced applications from portal")
#             self.action_fetch_unsynced_applications()
#         except Exception as e:
#             _logger.error(f"Automated fetch failed: {str(e)}")