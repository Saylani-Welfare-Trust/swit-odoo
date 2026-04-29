from unittest import result

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

import re
import logging
import requests
import json
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

# CNIC regular expression
cnic_pattern = r'^\d{5}-\d{7}-\d{1}$'
portal_sync_selection = [
    ('not_synced', 'Not Synced'),
    ('syncing', 'Syncing'),
    ('synced', 'Synced'),
    ('error', 'Sync Error'),
]

status_selection = [       
    ('draft', 'Draft'),
    ('completed', 'Completed'),
    ('send_for_inquiry', 'Send for Inquiry'),
    ('inquiry', 'Inquiry Officer'),
    ('ceo_approval', 'Approval(1)'),
    ('cfo_approval', 'Approval(2)'),
    ('approved', 'Approved'),
    ('sd_received', 'Security Received'),
    ('payment_received', 'Payment Received'),
    ('validate', 'Validate'),
    ('return', 'Return'),
    ('refund', 'Refund'),
    ('payment_return','Payment Return'),
    ('donate', 'Donate'),
    ('waiting_for_inventory_approval', 'Waiting for Inventory Approval'),
    ('recovered', 'Recovered'),
]

case_type_selection = [
    ('referral', 'Referral Case'),
    ('100_percent', '100% Case'),
    ('50_percent', '50% Case'),
    ('below_50_percent', 'Below 50% Case'),
]


class MedicalEquipment(models.Model):
    _name = 'medical.equipment'
    _description = "Medical Equipment"
    _inherit = ["mail.thread", "mail.activity.mixin"]



    donee_id = fields.Many2one('res.partner', string="Donee")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    picking_id = fields.Many2one('stock.picking', string="Picking")
    return_picking_id = fields.Many2one('stock.picking', string="Return Picking")
    recovery_picking_id = fields.Many2one('stock.picking', string="Recovery Picking")
    sd_slip_id = fields.Many2one('medical.security.deposit', string="SD Slip")
    last_sync_date = fields.Datetime('Last Sync Date')
    name = fields.Char('Name', default="New")
    country_code_id = fields.Many2one(related='donee_id.country_code_id', string="Country Code", store=True)
    mobile = fields.Char(related='donee_id.mobile', string="Mobile No.", store=True, size=10)
    city = fields.Char(related='donee_id.city', string="City", store=True)
    street = fields.Char(related='donee_id.street', string="Street", store=True, readonly=False)
    cnic_no = fields.Char(related='donee_id.cnic_no', string="CNIC No.", store=True, size=15)
    application_location_link = fields.Char(string="Applicant Location Link", store=True)
    portal_review_notes = fields.Text('Review Notes')
    is_actual_deposit_editable = fields.Boolean(
        compute='_compute_is_actual_deposit_editable',
        string='Is Editable',
        store=False
    )

    remaining_amount = fields.Monetary('Remaining Amount', currency_field='currency_id')
    inquiry_media = fields.Html(
            string="Inquiry Media",
            sanitize=False,   # IMPORTANT
        )
    
    general_remarks= fields.Text('General Remarks')
    remarks_approval1 = fields.Text('Approval(1) Remarks')
    remarks_approval2 = fields.Text('Approval(2) Remarks')
    employee_category_id = fields.Many2one('hr.employee.category', string="Employee Category", default=lambda self: self.env.ref('bn_welfare.inquiry_officer_hr_employee_category', raise_if_not_found=False).id)


    date_of_birth = fields.Date(related='donee_id.date_of_birth', string="Date of Birth", store=True)

    age = fields.Integer('Age',compute="_compute_age", store=True)

    gender = fields.Selection(related='donee_id.gender', string="Gender", store=True)
    state = fields.Selection(selection=status_selection, string="Status", default="draft")
    
    # Actual deposit percentage - determines case type automatically
    actual_deposit_percentage = fields.Float('Actual Deposit Percentage (%)', default=100.0)
    case_type = fields.Char('Case Type', compute='_compute_case_type', store=True)
    employee_id = fields.Many2one('hr.employee', string="Employee")
    loan_request_amount = fields.Float('Loan Request Amount')


    
    # Welfare portal fields for Below 50% cases
    welfare_portal_id = fields.Char('Portal ID', readonly=True)
    Portal_acknowledgment = fields.Boolean('Portal Acknowledgment' )
    
    total_amount = fields.Monetary('Total Amount', currency_field='currency_id',compute='_compute_total_amount',store=True)
    service_charges = fields.Monetary('Service Charges', currency_field='currency_id')

    is_donee_register = fields.Boolean('Is Donee Register', compute="_set_is_donee_register", store=True)

    approval_count = fields.Integer('Approval Count')
    approval_button_check = fields.Boolean('Approval Button Check', compute='_compute_approval_button_check')

    move_id = fields.Many2one('account.move', string="Account Move")

    medical_equipment_line_ids = fields.One2many('medical.equipment.line', 'medical_equipment_id', string="Medical Equipments")

    portal_sync_status = fields.Selection(selection=portal_sync_selection, string='Portal Sync Status', default='not_synced')
    portal_last_sync_message = fields.Text('Portal Last Sync Message')
    portal_application_id = fields.Char('Portal Application ID')
    is_synced = fields.Boolean('Is Synced')
    portal_donee_id = fields.Char('Portal Donee ID')
    initial_deposit_percentage = fields.Float(
        string="Initial Deposit %",
        readonly=True
    )

    @api.depends('state', 'case_type')
    def _compute_is_actual_deposit_editable(self):
        for record in self:
            if record.state in ['inquiry', 'draft', 'ceo_approval']:
                record.is_actual_deposit_editable = True
            elif record.state == 'completed' and record.case_type in  ['50_percent', '100_percent']:
                record.is_actual_deposit_editable = True
            else:
                record.is_actual_deposit_editable = False

    @api.constrains('actual_deposit_percentage')
    def _check_actual_deposit_percentage(self):
        for record in self:
            # Always check valid range
            if record.actual_deposit_percentage < 0 or record.actual_deposit_percentage > 100:
                raise ValidationError("Actual Deposit Percentage must be between 0 and 100.")

    @api.constrains('mobile')
    def _check_mobile_number(self):
        for rec in self:
            if rec.mobile:
                if not re.fullmatch(r"\d{10}", rec.mobile):
                    raise ValidationError(
                        "Mobile number must contain exactly 10 digits."
                    )


    @api.depends('date_of_birth')
    def _compute_age(self):
        for record in self:
            if record.date_of_birth:
                today = fields.Date.today()
                age = relativedelta(today, record.date_of_birth).years
                record.age = age
            else:
                record.age = 0

    @api.constrains('date_of_birth')
    def _check_age(self):
        for record in self:
            if record.date_of_birth:
                today = fields.Date.today()
                age = relativedelta(today, record.date_of_birth).years
                
                if age < 18:
                    raise ValidationError(
                        _("Age must be at least 18 years old. Current age: %s years") % age
                    )

    @api.depends('actual_deposit_percentage', 'state', 'initial_deposit_percentage')
    def _compute_case_type(self):
        for record in self:
            percentage = record.actual_deposit_percentage

            # ✅ Draft: fully dynamic
            if record.state == 'draft':
                if percentage == 100.0:
                    record.case_type = '100_percent'
                elif percentage == 50.0:
                    record.case_type = '50_percent'
                elif percentage < 50.0:
                    record.case_type = 'below_50_percent'
                else:
                    record.case_type = '50_percent'
                continue

            # ✅ Non-draft states: restrict downgrade
            if record.initial_deposit_percentage >= 50:
                # ❌ Prevent going below 50
                if percentage < 50.0:
                    record.case_type = '50_percent'
                    continue

            # ✅ Normal logic for allowed cases
            if percentage == 100.0:
                record.case_type = '100_percent'
            elif percentage == 50.0:
                record.case_type = '50_percent'
            elif percentage < 50.0:
                record.case_type = 'below_50_percent'
            else:
                record.case_type = '50_percent'

    @api.onchange('date_of_birth')
    def _onchange_date_of_birth(self):
        if self.date_of_birth:
            today = fields.Date.today()
            
            # Check for future dates
            if self.date_of_birth.year == today.year or self.date_of_birth.year > today.year:
                raise ValidationError('Invalid Date of Birth. Please enter a valid past date.')
            
            # Check age - must be 18 or older
            age = relativedelta(today, self.date_of_birth).years
            if age < 18:
                raise ValidationError(f'Age must be at least 18 years old. Current age: {age} years.')

    @api.constrains('cnic_no')
    def _check_cnic_no_format(self):
        for record in self:
            if record.cnic_no:
                if not re.match(cnic_pattern, record.cnic_no):
                    raise ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.cnic_no.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")


    def write(self, vals):
        if 'actual_deposit_percentage' in vals:
            for record in self:
                new_value = vals.get('actual_deposit_percentage')
                initial_value = record.initial_deposit_percentage

                # Always valid range
                if new_value < 0 or new_value > 100:
                    raise ValidationError("Value must be between 0 and 100.")

                if record.state != 'draft' and initial_value >= 50:
                    if new_value < 50:
                        raise ValidationError(
                            "You cannot change value below 50 because initial value was 50 or above."
                        )

        return super().write(vals)

            
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
    
    @api.depends('medical_equipment_line_ids.security_deposit', 'medical_equipment_line_ids.quantity')
    def _compute_total_amount(self):
        for record in self:
            total = 0.0
            for line in record.medical_equipment_line_ids:
                # The security_deposit is now calculated based on actual_deposit_percentage
                total += line.security_deposit * line.quantity
            record.total_amount = total

    @api.depends('donee_id')
    def _set_is_donee_register(self):
        for rec in self:
            rec.is_donee_register = False

            if rec.donee_id and rec.donee_id.state == 'register':
                rec.is_donee_register = True

    def action_register_donee(self):
        self.donee_id.action_register()
        self.is_donee_register = True
    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('medical_equipment') or ('New')
            
        if 'actual_deposit_percentage' in vals:
             vals['initial_deposit_percentage'] = vals['actual_deposit_percentage']

        return super(MedicalEquipment, self).create(vals)
    
    @api.depends('state', 'case_type', 'Portal_acknowledgment')
    def _compute_approval_button_check(self):
        for rec in self:
            # Condition 1: Completed and not below_50_percent
            condition_completed = (
                rec.state == 'completed' and 
                rec.case_type != 'below_50_percent'
            )
            # Condition 2: Inquiry and portal_acknowledgment is True
            condition_inquiry = (
                rec.state == 'inquiry' and 
                rec.Portal_acknowledgment is True  # or rec.portal_acknowledgment == True
            )
            # Button visible if either condition is True
            rec.approval_button_check = condition_completed or condition_inquiry
    def action_return(self):  
        """
        Automatically create return picking and update state
        """
        self.ensure_one()
        
        if not self.picking_id:
            raise ValidationError('No stock picking found to return. Please validate the equipment first.')
        
        if self.picking_id.state != 'done':
            raise ValidationError('Stock picking must be validated before returning.')
        
        # Create return wizard and generate return picking
        return_wizard = self.env['stock.return.picking'].with_context(
            active_id=self.picking_id.id,
            active_ids=[self.picking_id.id],
            active_model='stock.picking'
        ).create({})
        
        # Create the return picking
        result = return_wizard.create_returns()
        
        if result and result.get('res_id'):
            return_picking = self.env['stock.picking'].browse(result['res_id'])
            
            # Update medical equipment record
            self.write({
                'return_picking_id': return_picking.id,
                'state': 'return'
            })
            
            # Optional: Validate the return picking automatically
            return_picking.action_confirm()
            return_picking.action_assign()
            return_picking.button_validate()
            for product_line in self.medical_equipment_line_ids:
                for lot in product_line.lot_ids:
                    if lot.lot_consume:
                        lot.lot_consume = False
            # Show success message and open the return picking
            return True
        
        raise ValidationError('Failed to create return picking.')
    
    def action_validate(self):
        """
        Create a stock.picking record and assign operation type
        """
        # Ensure we're working with a single record
        self.ensure_one()
        
        operation_type = self.env.ref('bn_medical_equipment.medical_equipment_stock_picking_type')  # Outgoing shipment
        
        # Prepare stock picking values
        picking_vals = {
            'picking_type_id': operation_type.id,
            'location_id': operation_type.default_location_src_id.id,
            'location_dest_id': operation_type.default_location_dest_id.id,
            'origin': self.name,  # Reference to your medical equipment record
            'scheduled_date': fields.Datetime.now(),
            'move_ids': [(0, 0, {
                'name': f'Medical Equipment: {self.name}',
                'product_id': product_line.product_id.id,
                'product_uom_qty': product_line.quantity,
                'product_uom': product_line.product_id.uom_id.id,
                'location_id': operation_type.default_location_src_id.id,
                'location_dest_id': operation_type.default_location_dest_id.id,
                'lot_ids': [(6, 0, product_line.lot_ids.ids)],        
                'name': product_line.product_id.name,
            }) for product_line in self.medical_equipment_line_ids],
        }
        

        # Create the stock picking
        stock_picking = self.env['stock.picking'].create(picking_vals)  
        stock_picking.action_confirm()
        stock_picking.action_assign()
        stock_picking.button_validate()
        
        for product_line in self.medical_equipment_line_ids:
            for lot in product_line.lot_ids:
                if lot.lot_consume:
                    raise ValidationError(f"Lot {lot.name} has already been consumed. Please select a different lot.")
                lot.lot_consume = True
                
        # Link the stock picking to your medical equipment record
        self.write({
            'picking_id': stock_picking.id,
            'state': 'validate'  # Or whatever your next state should be
        })
        
        return True
    
    def action_approval(self):
        """
        Handle approval based on case type.
        - 100%: Single CEO approval → Approved (no remarks)
        - 50%: Two approvals (CEO → CFO) with remarks required for both
        - Below 50%: Same as 50% but also requires welfare portal & acknowledgment
        - Reference: Two approvals (CEO → CFO) with no remarks
        """
        self.ensure_one()
        
        case_type = self.case_type
        current_state = self.state
        
        # Helper to check if case requires two approvals
        requires_two_approvals = case_type in ['50_percent', 'below_50_percent', 'reference']
        requires_remarks_ceo = case_type in ['50_percent', 'below_50_percent']
        requires_remarks_cfo = case_type in ['50_percent', 'below_50_percent']
        
        # Special validations for below_50_percent
        if case_type == 'below_50_percent':
            if not self.welfare_portal_id:
                raise ValidationError('Welfare Portal ID must be synced before approval for Below 50% cases.')
            if not self.Portal_acknowledgment:
                raise ValidationError('Welfare acknowledgment must be received before approval.')
        
        # State transitions
        if current_state in ['completed', 'inquiry']:
            # First approval: from completed/inquiry to ceo_approval
            if requires_remarks_ceo and not self.remarks_approval1:
                raise ValidationError('Approval(1) remarks are required for this case type.')
            self.write({'state': 'ceo_approval'})
            
        elif current_state == 'ceo_approval':
            # Second approval: from ceo_approval to cfo_approval or approved
            if requires_two_approvals:
                # Need CFO approval
                if requires_remarks_cfo and not self.remarks_approval2:
                    raise ValidationError('Approval(2) remarks are required for this case type.')
                self.write({'state': 'cfo_approval'})
            else:
                # 100% case: directly approved
                self.write({'state': 'cfo_approval'})
                
        elif current_state == 'cfo_approval':
            # Final approval to approved
            self.write({'state': 'cfo_approval'})
            
        else:
            raise ValidationError('This record has already been approved or is in an invalid state.')
    
        self.approval_count += 1
    
    
    def action_sync_welfare_portal(self):
        """
        Sync Below 50% cases to welfare portal - follows welfare.py pattern
        """
        if not self:
            raise UserError("Please select at least one record.")
        
        invalid = self.filtered(lambda r: r.case_type != 'below_50_percent')
        if invalid:
            raise UserError("Only Below 50% cases can be synced to welfare portal.")
        # self.state = 'inquiry'
        
        success_msgs = []
        error_msgs = []
        
        for rec in self:
            if not rec.donee_id or not rec.donee_id.name:
                error_msgs.append(f"[{rec.display_name}] Donee is required.")
                continue
            if not rec.cnic_no and not rec.donee_id.mobile:
                error_msgs.append(f"[{rec.display_name}] CNIC or Mobile is required.")
                continue
            
            try:
                # Step 1: Check if donee exists in portal
                donee_exists = rec._check_donee_exists_in_portal()  
                
                # Step 2: Create donee if needed
                if not donee_exists:
                    donee_data = rec._create_donee_in_portal()
                    portal_donee_id = donee_data.get('id')
                else:
                    portal_donee_id = donee_exists.get('id')
                
                # Step 3: Create application in portal
                portal_application = rec._create_me_portal_application()
                portal_application_id = portal_application.get('id')
                
                # Step 4: Mark as synced in portal
                # rec._mark_me_application_synced()
                
                # Step 5: Update record with portal information (like welfare does)
                rec.write({
                    'welfare_portal_id': portal_application_id,
                    # 'Portal_acknowledgment': True,
                    'last_sync_date': self.last_sync_date,
                    'state': 'send_for_inquiry',

                })
                
                result_message = f"✅ Successfully synced to Welfare Portal. Application ID: {portal_application_id}"
                success_msgs.append(f"[{rec.display_name}] {result_message}")
                
            except Exception as e:
                error_message = f"[{rec.display_name}] Portal sync failed: {str(e)}"
                error_msgs.append(error_message)
        
        summary = ""
        if success_msgs:
            summary += "<b>Success:</b><br/>" + "<br/>".join(success_msgs) + "<br/>"
        if error_msgs:
            summary += "<b>Errors:</b><br/>" + "<br/>".join(error_msgs)
        if not summary:
            summary = "No records processed."
        
        return self._show_notification('Welfare Portal Sync Results', summary, 'info')

    def _create_donee_in_portal(self):
        """Create donee in welfare portal"""
        try:
            endpoint = self.env.company.create_donee_endpoint
            data = {
                "json": {
                    "name": self.donee_id.name or '',
                    "whatsapp": self.donee_id.mobile or '',
                    "cnic": (
                        self.donee_id.cnic_no.replace("-", "")
                        if self.donee_id.cnic_no else ""
                    ),
                    "odooId": self.donee_id.id
                }
            }
            result = self._make_welfare_api_call(endpoint, 'POST', data)
            return result
        except Exception as e:
            raise ValidationError(f"Failed to create donee in welfare portal: {str(e)}")

    
    def clean_url(self, url) :
        return (
            url.strip()
            .replace('\u200b', '')   # zero-width space
            .replace('\ufeff', '')   # BOM
            .replace('\u00a0', '')   # non-breaking space
        )
        
    def _make_welfare_api_call(self, endpoint, method='POST', data=None):
        """Make API call to welfare/Sadqa portal - similar to welfare.py pattern"""
        url = self.clean_url(f"{self.env.company.welfare_url}{endpoint}")
        headers = {
            'x-odoo-auth-key': f'{self.env.company.odoo_auth_key}',
            'Content-Type': 'application/json'
        }
        
        if data is not None:
            try:
                # Convert non-serializable types (dates, datetimes, Decimals, etc.) to JSON-safe values
                data = json.loads(json.dumps(data, default=str))
            except Exception as e:
                _logger.error("Failed to prepare JSON payload: %s", e)
                raise UserError(_("Failed to prepare request payload: %s") % e)
        
        _logger.info(f"Making Welfare API call to {url} with method {method} and data: {data}")
        try:
            if method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=30)
            else:
                response = requests.get(url, headers=headers, timeout=30)
            
            response.raise_for_status()
            result = response.json()
            _logger.info(f"URL: {url} Data: {data} api response: {result}")
            
            if not result.get('json', {}):
                raise ValidationError(f"Unexpected API response format: {result}")
                error_msg = result.get('error', 'Unknown error occurred')
                raise Exception(f"Portal API Error: {error_msg}")
            
            return result.get('json', {})
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"Welfare API Request failed: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise ValidationError(f"An error occurred while processing the welfare portal request: {str(result)}")
            _logger.error(f"Welfare API Processing failed: {str(e)}")
            raise e
    
    def _show_notification(self, title, message, notification_type='info'):
        """Show notification dialog to user"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': notification_type,
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},

            }
        }
    
    def action_acknowledge_welfare_portal(self):
        """
        Mark welfare portal acknowledgment received for Below 50% cases
        """
        self.ensure_one()
        
        if self.case_type != 'below_50_percent':
            raise ValidationError('Only Below 50% cases can receive welfare acknowledgment.')
        
        self.write({'Portal_acknowledgment': True})
        
    def action_show_picking(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Opertaion',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.picking_id.id,
            'target': 'current',
        }
    
    def action_show_return_picking(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Return',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.return_picking_id.id,
            'target': 'current',
        }
    
    def action_show_recovery_picking(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Recovery',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.recovery_picking_id.id,
            'target': 'current',
        }
    
    def action_show_sd_slip(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Recovery',
            'res_model': 'medical.security.deposit',
            'view_mode': 'form',
            'res_id': self.sd_slip_id.id,
            'context': {
                'edit': 0
            },
            'target': 'current',
        }
    
    def action_show_move(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.move_id.id,
            'target': 'current',
        }

    @api.model
    def create_me_record(self, data):
        product_lines = []

        for line in data['order_lines']:
            # Assuming 'product_id' is a valid product ID
            product_lines.append((0, 0, {
                'product_id': line['product_id'],
                'quantity': line['quantity'],
            }))
        
        me = self.env['medical.equipment'].create({
            'donee_id': data['donee_id'],
            'medical_equipment_line_ids': product_lines
        })

        for line in me.medical_equipment_line_ids:
            base_price = line.product_id.lst_price
            taxes = line.product_id.taxes_id

            total_price_incl_tax = base_price

            for tax in taxes:
                if tax.amount_type == 'percent':
                    tax_amount = base_price * (tax.amount / 100)

                    total_price_incl_tax += tax_amount
                else:
                    total_price_incl_tax += tax.amount

            line.security_deposit = total_price_incl_tax * line.quantity

        me.calculate_amount()
       
        return{
            "status": "success",
            "id": me.id
        }
    
    @api.model
    def get_me_record(self, data):
        """Fetch ME record by name and return product information"""
        # Search for the ME record
        me = self.sudo().search([('name', '=', data['name']), ('state', '!=', 'paid')], limit=1)
        
        if not me:
            return {
                "status": "error",
                "body": f"Donation Home Service record with reference {data['name']} not found."
            }
        
        if me.state not in ['gate_pass', 'gate_in']:
            return {
                "status": "error",
                "body": f"Current status of {data['name']} is in a {me.state.capitalize()}."
            }
        
        # Prepare product data for POS
        products_data = []
        
        # Add regular product lines
        for line in me.medical_equipment_line_ids:
            product = line.product_id
            products_data.append({
                'product_id': product.id,
                'name': product.name,
                'quantity': line.quantity,
                'price': product.lst_price,
                'default_code': product.default_code,
                'category': product.categ_id.name if product.categ_id else ''
            })
        
        return {
            'id': me.id,
            'name': me.name,
            'donee_id': me.donee_id.id if me.donee_id else False,
            'donor_name': me.donee_id.name if me.donee_id else '',
            'products': products_data,
            'success': True
        }
    
    def action_recovery(self):
        """
        Automatically create recovery picking and update state
        """
        self.ensure_one()
        
        if not self.picking_id:
            raise ValidationError('No stock picking found to return. Please validate the equipment first.')
        if self.return_picking_id:
            raise ValidationError('This record picking has already been recovered.')
        
        if self.picking_id.state != 'done':
            raise ValidationError('Stock picking must be validated before returning.')
        
        # Create return wizard and generate recovery picking
        return_wizard = self.env['stock.return.picking'].with_context(
            active_id=self.picking_id.id,
            active_ids=[self.picking_id.id],
            active_model='stock.picking'
        ).create({})
        
        # Create the recovery picking
        result = return_wizard.create_returns()
        
        if result and result.get('res_id'):
            recovery_picking = self.env['stock.picking'].browse(result['res_id'])
            recovery_picking.origin = self.name
            recovery_picking.is_medical_recovery = True
            
            # Update medical equipment record
            self.write({
                'recovery_picking_id': recovery_picking.id,
                'state': 'waiting_for_inventory_approval'
            })
            
            # Show success message and open the recovery picking
            return True
        
        raise ValidationError('Failed to create recovery picking.')
    
    def action_refund(self):
        self.state = 'refund'
    
    def action_donate(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Product Wizard',
            'res_model': 'medical.equipment.donation',
            'view_mode': 'form',
            'context': {
                'default_medical_equipment_id': self.id,
                'default_amount': self.total_amount
            },
            'target': 'new',
        }


    def _find_matching_application(self, applications):
        """Find matching application from portal data"""
        for app in applications:
            # Match by CNIC (most reliable)
            # _logger.info(f"Checking application: {app} and id is system {self.id} portal {app.get('id')}" )
            if app.get('odooId') == self.id and app.get('department') == "medical":
                return app
            # # Match by name and WhatsApp
            # if (app.get('name') == self.donee_id.name and 
            #     app.get('whatsapp') == self.donee_id.mobile):
            #     return app
        return None            
    def action_complete(self):
        if not self.medical_equipment_line_ids:
            raise ValidationError(_('You must add Medical Equipment Line before completing.'))
        self.state = 'completed'
            

    def _mark_application_synced(self):
        """Mark application as synced in portal"""
        data = {
                "json":{

                "odooId": self.id,
                "department": "medical",
            }
        }
        result = self._make_sadqa_api_call(self.env.company.mark_application_endpoint, 'POST', data)
        return result


    def _handle_existing_application(self, portal_application):
            """Handle existing application found in portal"""
            # Mark application as synced in portal
            synced_application = self._mark_application_synced()
            
            return {
            'action': 'linked_existing',
            'application_id': portal_application.get('id'),
            'message': f"✅ Existing application linked successfully. Application ID: {portal_application.get('id')}",
            'details': f"Donee: {portal_application.get('name')}"
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
                    'is_synced': False,
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

    def _update_sync_status_success(self, result):
        """Update successful sync status"""
        self.write({
            'portal_sync_status': 'synced',
            'portal_last_sync_message': f"Success: {result['message']} at {fields.Datetime.now()}"
        })
   
    def _make_sadqa_api_call(self, endpoint, method='POST', data=None):
        """Make API call to Sadqa Jaria portal"""
        # base_url = 'https://backend.switsjmm.com'
        url = f"{self.env.company.welfare_url}{endpoint}"
        headers = self._get_sadqa_api_headers()

        url = self.clean_url(url)

        if data is not None:
            try:
                # Convert non-serializable types (dates, datetimes, Decimals, etc.) to JSON-safe values
                data = json.loads(json.dumps(data, default=str))
            except Exception as e:
                _logger.error("Failed to prepare JSON payload: %s", e)
                raise UserError(_("Failed to prepare request payload: %s") % e)

        _logger.info(f"Making Sadqa Jaria API call to {url} with method {method} and data: {data}")
        try:
            if data is None :
                response = requests.post(url, headers=headers, timeout=30)
            else :
                response = requests.post(url, headers=headers, json=data, timeout=30)

            
            response.raise_for_status()
            result = response.json()
            _logger.info(f" URL: {url} Data: {data}  api response : {result}")

            
            if not result.get('json', {}):
                raise ValidationError(f"Unexpected API response format: {result}")
                error_msg = result.get('error', 'Unknown error occurred')
                raise Exception(f"Portal API Error: {error_msg}")
                
            return result.get('json', {})
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"Sadqa Jaria API Request failed: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise ValidationError(f"An error occurred while processing the Sadqa Jaria portal request: {str(result)}")
            _logger.error(f"Sadqa Jaria API Processing failed: {str(e)}")e
            raise e
    def _get_sadqa_api_headers(self):
        """Get API authentication headers"""
        return {
            'x-odoo-auth-key': f'{self.env.company.odoo_auth_key}',
            'Content-Type': 'application/json'
        }



    def action_check_portal_status(self):
        """Check current status in portal"""
        self.ensure_one()
        
     
        donee_data = self._check_donee_exists_in_portal()

            
        if donee_data:
                message = f"✅ Donee exists in portal. Name: {donee_data.get('name')}"

        else:
            donee_in_portal = self._create_donee_in_portal()
            # message = "✅ Donee created in portal"  # Add this line
        # Check for applications
        application = self._search_portal_applications()
        raise UserError(str(application))
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
            self.write({"welfare_portal_id": application.get('id')})
            self.write({"Portal_acknowledgment": application.get('welfareAcknowledgment', True)})
            self.write({"state":"inquiry"})
            result = self._handle_existing_application(application)
            message = f" | 📋 application status: {app_state} "
            if result and isinstance(result, dict) and 'message' in result:
                message += f" | 📋 {result['message']} "
            else:
                message += f" | 📋 No applications found"     # type: ignore
        return self._show_notification('Portal Status Check', message, 'info')
    def _search_portal_applications(self):
        """Search for matching applications in portal"""
        try:
            result = self._make_sadqa_api_call(self.env.company.search_endpoint)
            applications = result
            raise ValidationError(str(applications))
            if applications:
                _logger.info(f"Unsynced applications found: {applications}")
                # Find matching application based on donee information
                matching_app = self._find_matching_application(applications)
                return matching_app
            return None
            
        except Exception as e:
            raise ValidationError(str(e))
            _logger.warning(f"Error occurred while searching portal applications: {str(e)}")
            return None


    def create_portal_application(self):
        """Create application in Sadqa Jaria portal"""
        # self.ensure_one()
        data_list = []
        for line in self.medical_equipment_line_ids:
            data_list.append({
                "medicalEquipmentCategoryId": line.medical_equipment_category_id,
                "productId": line.product_id.display_name,
                "quantity": line.quantity,
                "baseSecurityDeposit": line.base_security_deposit,
                "actualDepositPercentage": line.actual_deposit_percentage,
                "securityDeposit": line.security_deposit,
        })
        # raise ValidationError(str(data_list))
        data = {
            "json": {
                "applicationData": {
                    "odooId": self.id,
                    "doneeOdooId": self.donee_id.id,
                    "inquiryOfficerOdooId": self.employee_id.id,
                    "department": "medical",
                    "form": {
                        "category": "medical",
                        "subcategory": "medical",
                        "date": fields.Date.today().strftime("%d-%m-%Y"),
                        "loanRequestAmount": self.loan_request_amount,
                        "applicationInformation": {
                            "name": self.donee_id.name,
                            "fatherName": self.donee_id.father_name,
                            "cnic": self.cnic_no,
                            "phoneNumber": self.donee_id.mobile,
                            "whatsappNumber": self.donee_id.mobile,
                            "applicantLocationLink": self.application_location_link,
                        },
                        "medicalInfo": {
                            "state": self.state ,
                            "actualDepositPercentage": self.actual_deposit_percentage,
                            "caseType": self.case_type,
                            "totalAmount": self.total_amount,
                            "serviceCharges": self.service_charges,
                            "remarks": self.general_remarks,
                            "welfarePortalId": self.welfare_portal_id,
                            "welfareAcknowledgment": self.Portal_acknowledgment,
                            "medicalEquipmentLines": data_list,
                        },
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
    