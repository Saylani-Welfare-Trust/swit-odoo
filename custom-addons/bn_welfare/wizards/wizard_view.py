from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class WelfareFieldsWizard(models.TransientModel):
    _name = 'welfare.fields.wizard'
    _description = 'Welfare Fields Wizard - Full Page View'
    
    welfare_id = fields.Many2one('welfare', string='Welfare Record', required=True)
    
    # Basic Information
    name = fields.Char('Name')
    cnic_no = fields.Char('CNIC No.')
    father_name = fields.Char('Father Name')
    father_cnic_no = fields.Char('Father CNIC No.')
    old_system_id = fields.Char('Old System ID')
    applicantLocationLink = fields.Char('Applicant Location Link')
    date = fields.Date('Date')
    cnic_expiration_date = fields.Date('CNIC Expiration Date')
    order_type = fields.Selection([
        ('one_time', 'One Time'),
        ('recurring', 'Recurring'),
    ], string="Order Type")
    is_individual = fields.Boolean('Is Individual')
    
    # Remarks
    hod_remarks = fields.Text('HOD Remarks')
    member_remarks = fields.Text('Member Remarks')
    committee_remarks = fields.Text('Committee Remarks')
    rejection_remarks = fields.Text('Rejection Remarks')
    
    # Portal Details
    portal_application_id = fields.Char('Portal Application ID')
    portal_donee_id = fields.Char('Portal Donee ID')
    last_sync_date = fields.Datetime(string='Last Sync Date')
    is_synced = fields.Boolean('Is Synced')
    portal_sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('syncing', 'Syncing'),
        ('synced', 'Synced'),
        ('error', 'Sync Error'),
    ], string='Portal Sync Status')
    portal_last_sync_message = fields.Text('Portal Last Sync Message')
    portal_review_notes = fields.Text('Review Notes')
    inquiry_media = fields.Html(string="Inquiry Media", sanitize=False)
    
    # Employee Information
    designation = fields.Char('Designation')
    company_name = fields.Char('Company Name')
    company_phone = fields.Char('Company Phone No.')
    company_address = fields.Char('Company Address')
    service_duration = fields.Integer('Service Duration (In Years)')
    monthly_salary = fields.Monetary('Monthly Salary', currency_field='currency_id')
    
    # Residency Details
    residence_type = fields.Selection([
        ('owned', 'Owned'),
        ('shared', 'Shared'),
        ('rented', 'Rented'),
    ], string="Residence Type")
    home_phone_no = fields.Char('Home Phone No.')
    landlord_cnic_no = fields.Char('CNIC No. of Landlord')
    landlord_mobile = fields.Char('Mobile No. of Landlord')
    landlord_name = fields.Char('Name of Landlord / Owner')
    rental_shared_duration = fields.Integer('Rental / Shared Duration')
    per_month_rent = fields.Float('Per month Rent')
    gas_bill = fields.Float('Cumulative Gas Bill of 6 Months (Total)')
    electricity_bill = fields.Float('Cumulative Electricity Bill of 6 Months (total)')
    home_other_info = fields.Text('Other info / Address of Landlord')
    
    # Financial Information
    monthly_income = fields.Float('Monthly Income')
    outstanding_amount = fields.Float('Outstanding Amount')
    monthly_household_expense = fields.Float('Monthly Household Expenses')
    bank_account = fields.Selection([
        ('no', 'No'),
        ('yes', 'Yes'),
    ], string="Bank Account")
    bank_name = fields.Char('Bank Name')
    account_no = fields.Char('Account No')
    institute_name = fields.Char('Institution Name')
    other_loan = fields.Selection([
        ('no', 'No'),
        ('yes', 'Yes'),
    ], string="Any Other Loan?")
    
    # Other Information
    aid_from_other_organization = fields.Selection([
        ('no', 'No'),
        ('yes', 'Yes'),
    ], string="Aid from Other Organisation")
    have_applied_swit = fields.Selection([
        ('no', 'No'),
        ('yes', 'Yes'),
    ], string="Have you ever applied with SWIT?")
    details_1 = fields.Text('Details 1')
    details_2 = fields.Text('Details 2')
    driving_license = fields.Selection([
        ('no', 'No'),
        ('yes', 'Yes'),
    ], string="Driving License")
    
    # Request Details
    loan_request_amount = fields.Float('Loan Request Amount')
    loan_tenure_expected = fields.Selection([
        ('12M', '12 Months'),
        ('24M', '24 Months'),
        ('36M', '36 Months'),
        ('other', 'Other'),
    ], string='Loan Tenure Expected')
    security_offered = fields.Char('Security Offered')
    
    # Family Detail
    dependent_person = fields.Integer('No. of Dependents')
    household_member = fields.Integer('Household members')
    
    # Institution Details
    institution_category = fields.Selection([
        ('masjid', 'Masjid'),
        ('madrasa', 'Madrasa'),
    ], string='Institution Category')
    subcategory = fields.Char(string='Subcategory')
    
    currency_id = fields.Many2one('res.currency', 'Currency')
    
    # Binary Fields (Attachments)
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
    
    # HTML Display fields for One2many data
    welfare_lines_html = fields.Html(string='Disbursement Items', readonly=True)
    education_lines_html = fields.Html(string='Education Information', readonly=True)
    family_lines_html = fields.Html(string='Family Details', readonly=True)
    guarantor_lines_html = fields.Html(string='Guarantor Information', readonly=True)
    recurring_lines_html = fields.Html(string='Recurring Welfare Lines', readonly=True)
    committee_members_html = fields.Html(string='Committee Members', readonly=True)
    teachers_html = fields.Html(string='Teachers', readonly=True)
    masjid_html = fields.Html(string='Masjid Details', readonly=True)
    madrasa_html = fields.Html(string='Madrasa Details', readonly=True)
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        welfare_id = self.env.context.get('active_id')
        if welfare_id:
            welfare = self.env['welfare'].browse(welfare_id)
            res['welfare_id'] = welfare.id
            
            # Copy simple fields
            for field_name in fields_list:
                if field_name not in ['welfare_id', 'welfare_lines_html', 'education_lines_html', 
                                       'family_lines_html', 'guarantor_lines_html', 'recurring_lines_html',
                                       'committee_members_html', 'teachers_html', 'masjid_html', 'madrasa_html']:
                    if hasattr(welfare, field_name):
                        res[field_name] = getattr(welfare, field_name)
            
            # Build HTML table for Welfare Lines
            if welfare.welfare_line_ids:
                html = '<table class="table" style="width:100%; border-collapse: collapse;">'
                html += '<thead><tr style="background-color: #f0f0f0;">'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Product</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Quantity</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Amount</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Total</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Collection Date</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Collection Point</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Status</th>'
                html += '</tr></thead><tbody>'
                for line in welfare.welfare_line_ids:
                    html += '<tr>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{line.product_id.name if line.product_id else ""}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{line.quantity}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{line.amount}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{line.total_amount}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{line.collection_date}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{line.collection_point}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{line.state}</td>'
                    html += '</tr>'
                html += '</tbody></table>'
                res['welfare_lines_html'] = html
            else:
                res['welfare_lines_html'] = '<p>No disbursement items</p>'
            
            # Build HTML table for Education Lines
            if welfare.educaiton_line_ids:
                html = '<table class="table" style="width:100%; border-collapse: collapse;">'
                html += '<thead><tr style="background-color: #f0f0f0;">'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Degree</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Institution</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Year</th>'
                html += '</tr></thead><tbody>'
                for edu in welfare.educaiton_line_ids:
                    html += '<tr>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{edu.display_name}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;"></td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;"></td>'
                    html += '</tr>'
                html += '</tbody></table>'
                res['education_lines_html'] = html
            else:
                res['education_lines_html'] = '<p>No education records</p>'
            
            # Build HTML table for Family Lines
            if welfare.family_line_ids:
                html = '<table class="table" style="width:100%; border-collapse: collapse;">'
                html += '<thead><tr style="background-color: #f0f0f0;">'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Name</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Relation</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Age</th>'
                html += '</tr></thead><tbody>'
                for family in welfare.family_line_ids:
                    html += '<tr>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{family.display_name}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;"></td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;"></td>'
                    html += '</tr>'
                html += '</tbody></table>'
                res['family_lines_html'] = html
            else:
                res['family_lines_html'] = '<p>No family members</p>'
            
            # Build HTML table for Guarantor Lines
            if welfare.guarantor_line_ids:
                html = '<table class="table" style="width:100%; border-collapse: collapse;">'
                html += '<thead><tr style="background-color: #f0f0f0;">'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Name</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Relation</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">CNIC</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Mobile</th>'
                html += '</tr></thead><tbody>'
                for guarantor in welfare.guarantor_line_ids:
                    html += '<tr>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{guarantor.display_name}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;"></td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;"></td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;"></td>'
                    html += '</tr>'
                html += '</tbody></table>'
                res['guarantor_lines_html'] = html
            else:
                res['guarantor_lines_html'] = '<p>No guarantors</p>'
            
            # Build HTML table for Recurring Lines
            if welfare.welfare_recurring_line_ids:
                html = '<table class="table" style="width:100%; border-collapse: collapse;">'
                html += '<thead><tr style="background-color: #f0f0f0;">'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Collection Date</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Product</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Amount</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Status</th>'
                html += '</tr></thead><tbody>'
                for recurring in welfare.welfare_recurring_line_ids:
                    html += '<tr>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{recurring.collection_date}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{recurring.product_id.name if recurring.product_id else ""}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{recurring.amount}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{recurring.state}</td>'
                    html += '</tr>'
                html += '</tbody></table>'
                res['recurring_lines_html'] = html
            else:
                res['recurring_lines_html'] = '<p>No recurring lines</p>'
            
            # Committee Members
            if welfare.committee_member_ids:
                html = '<table class="table" style="width:100%; border-collapse: collapse;">'
                html += '<thead><tr style="background-color: #f0f0f0;">'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Member</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Role</th>'
                html += '</tr></thead><tbody>'
                for member in welfare.committee_member_ids:
                    html += '<tr>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{member.display_name}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;"></td>'
                    html += '</tr>'
                html += '</tbody></table>'
                res['committee_members_html'] = html
            else:
                res['committee_members_html'] = '<p>No committee members</p>'
            
            # Teachers
            if welfare.teacher_ids:
                html = '<table class="table" style="width:100%; border-collapse: collapse;">'
                html += '<thead><tr style="background-color: #f0f0f0;">'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Name</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Qualification</th>'
                html += '</tr></thead><tbody>'
                for teacher in welfare.teacher_ids:
                    html += '<tr>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{teacher.display_name}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;"></td>'
                    html += '</tr>'
                html += '</tbody></table>'
                res['teachers_html'] = html
            else:
                res['teachers_html'] = '<p>No teachers</p>'
            
            # Masjid
            if welfare.masjid_id:
                html = '<table class="table" style="width:100%; border-collapse: collapse;">'
                html += '<thead><tr style="background-color: #f0f0f0;">'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Name</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Address</th>'
                html += '</tr></thead><tbody>'
                for masjid in welfare.masjid_id:
                    html += '<tr>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{masjid.display_name}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;"></td>'
                    html += '</tr>'
                html += '</tbody></table>'
                res['masjid_html'] = html
            else:
                res['masjid_html'] = '<p>No masjid details</p>'
            
            # Madrasa
            if welfare.madrasa_id:
                html = '<table class="table" style="width:100%; border-collapse: collapse;">'
                html += '<thead><tr style="background-color: #f0f0f0;">'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Name</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Address</th>'
                html += '</tr></thead><tbody>'
                for madrasa in welfare.madrasa_id:
                    html += '<tr>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{madrasa.display_name}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;"></td>'
                    html += '</tr>'
                html += '</tbody></table>'
                res['madrasa_html'] = html
            else:
                res['madrasa_html'] = '<p>No madrasa details</p>'
        
        return res
    
    def action_approve(self):
        """Handle approval based on current state"""
        self.ensure_one()
        welfare = self.welfare_id
        
        # First save all changes
        fields_to_copy = [
            'name', 'cnic_no', 'father_name', 'father_cnic_no', 'old_system_id',
            'applicantLocationLink', 'date', 'cnic_expiration_date',
            'designation', 'company_name', 'company_phone', 'company_address', 
            'service_duration', 'monthly_salary', 'residence_type', 'home_phone_no', 
            'landlord_cnic_no', 'landlord_mobile', 'landlord_name', 'rental_shared_duration', 
            'per_month_rent', 'gas_bill', 'electricity_bill', 'home_other_info', 
            'monthly_income', 'outstanding_amount', 'monthly_household_expense', 
            'bank_account', 'bank_name', 'account_no', 'institute_name', 'other_loan',
            'aid_from_other_organization', 'have_applied_swit', 'details_1', 'details_2',
            'driving_license', 'loan_request_amount', 'loan_tenure_expected',
            'security_offered', 'dependent_person', 'household_member',
            'institution_category', 'subcategory', 'currency_id', 'order_type', 'is_individual',
            'portal_application_id', 'portal_donee_id', 'last_sync_date', 'is_synced',
            'portal_sync_status', 'portal_last_sync_message', 'portal_review_notes', 'inquiry_media',
            'application_form', 'application_form_name', 'frc', 'frc_name',
            'electricity_bill_file', 'electricity_bill_name', 'gas_bill_file', 'gas_bill_name',
            'family_cnic', 'family_cnic_name'
        ]
        
        update_vals = {}
        for field in fields_to_copy:
            if hasattr(self, field):
                update_vals[field] = getattr(self, field)
        
        if update_vals:
            welfare.write(update_vals)
        
        # Handle approval based on current state
        if welfare.state == 'inquiry':
            # Check committee remarks
            if not self.committee_remarks:
                raise ValidationError('Please enter Committee Remarks before approval.')
            welfare.write({'committee_remarks': self.committee_remarks})
            welfare.action_committee_approval()  # This moves to hod_approve
            message = 'Application approved by Committee and sent to HOD'
            
        elif welfare.state == 'committee_approval':
            # Check HOD remarks
            if not self.hod_remarks:
                raise ValidationError('Please enter HOD Remarks before approval.')
            welfare.write({'hod_remarks': self.hod_remarks})
            welfare.action_move_to_hod()  # This moves to mem_approve
            message = 'Application approved by HOD and sent to Member'
            
            
        else:
            raise ValidationError(f'Cannot approve from state: {welfare.state}')
        
        return {
            'type': 'ir.actions.act_window_close',
            'context': self.env.context,
        }
    
    def action_save_and_close(self):
        self.ensure_one()
        welfare = self.welfare_id
        
        fields_to_copy = [
            'name', 'cnic_no', 'father_name', 'father_cnic_no', 'old_system_id',
            'applicantLocationLink', 'date', 'cnic_expiration_date', 'hod_remarks',
            'member_remarks', 'committee_remarks', 'rejection_remarks', 'designation',
            'company_name', 'company_phone', 'company_address', 'service_duration',
            'monthly_salary', 'residence_type', 'home_phone_no', 'landlord_cnic_no',
            'landlord_mobile', 'landlord_name', 'rental_shared_duration', 'per_month_rent',
            'gas_bill', 'electricity_bill', 'home_other_info', 'monthly_income',
            'outstanding_amount', 'monthly_household_expense', 'bank_account',
            'bank_name', 'account_no', 'institute_name', 'other_loan',
            'aid_from_other_organization', 'have_applied_swit', 'details_1', 'details_2',
            'driving_license', 'loan_request_amount', 'loan_tenure_expected',
            'security_offered', 'dependent_person', 'household_member',
            'institution_category', 'subcategory', 'currency_id', 'order_type', 'is_individual',
            'portal_application_id', 'portal_donee_id', 'last_sync_date', 'is_synced',
            'portal_sync_status', 'portal_last_sync_message', 'portal_review_notes', 'inquiry_media',
            'application_form', 'application_form_name', 'frc', 'frc_name',
            'electricity_bill_file', 'electricity_bill_name', 'gas_bill_file', 'gas_bill_name',
            'family_cnic', 'family_cnic_name'
        ]
        
        update_vals = {}
        for field in fields_to_copy:
            if hasattr(self, field):
                update_vals[field] = getattr(self, field)
        
        if update_vals:
            welfare.write(update_vals)
        
        return {'type': 'ir.actions.act_window_close'}
    
    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}