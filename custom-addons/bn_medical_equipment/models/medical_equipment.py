from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

import re
import logging
import requests
import json

_logger = logging.getLogger(__name__)

# CNIC regular expression
cnic_pattern = r'^\d{5}-\d{7}-\d{1}$'

status_selection = [       
    ('draft', 'Draft'),
    ('ceo_approval', 'CEO Approval'),
    ('cfo_approval', 'CFO Approval'),
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


    donee_id = fields.Many2one('res.partner', string="Donee")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    picking_id = fields.Many2one('stock.picking', string="Picking")
    return_picking_id = fields.Many2one('stock.picking', string="Return Picking")
    recovery_picking_id = fields.Many2one('stock.picking', string="Recovery Picking")
    sd_slip_id = fields.Many2one('medical.security.deposit', string="SD Slip")

    name = fields.Char('Name', default="New")
    country_code_id = fields.Many2one(related='donee_id.country_code_id', string="Country Code", store=True)
    mobile = fields.Char(related='donee_id.mobile', string="Mobile No.", store=True, size=10)
    city = fields.Char(related='donee_id.city', string="City", store=True)
    street = fields.Char(related='donee_id.street', string="Street", store=True)
    cnic_no = fields.Char(related='donee_id.cnic_no', string="CNIC No.", store=True, size=15)
    
    remarks = fields.Text('Remarks')

    date_of_birth = fields.Date(related='donee_id.date_of_birth', string="Date of Birth", store=True)

    age = fields.Integer('Age',compute="_compute_age", store=True)

    gender = fields.Selection(related='donee_id.gender', string="Gender", store=True)
    state = fields.Selection(selection=status_selection, string="Status", default="draft")
    
    # Actual deposit percentage - determines case type automatically
    actual_deposit_percentage = fields.Float('Actual Deposit Percentage (%)', default=100.0)
    case_type = fields.Char('Case Type', compute='_compute_case_type', store=True)
    
    # Welfare portal fields for Below 50% cases
    welfare_portal_id = fields.Char('Welfare Portal ID', readonly=True)
    welfare_acknowledgment = fields.Boolean('Welfare Portal Acknowledgment')
    
    total_amount = fields.Monetary('Total Amount', currency_field='currency_id',compute='_compute_total_amount',store=True)
    service_charges = fields.Monetary('Service Charges', currency_field='currency_id')

    is_donee_register = fields.Boolean('Is Donee Register', compute="_set_is_donee_register", store=True)

    approval_count = fields.Integer('Approval Count')

    move_id = fields.Many2one('account.move', string="Account Move")

    medical_equipment_line_ids = fields.One2many('medical.equipment.line', 'medical_equipment_id', string="Medical Equipments")


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
                # Get today's date
                today = fields.Date.today()
                age = today.year - record.date_of_birth.year
                record.age = age
            else:
                record.age = 0  # Default value when there's no birth date

    @api.depends('actual_deposit_percentage')
    def _compute_case_type(self):
        """
        Auto-determine case type based on actual deposit percentage
        100% = 100% Case
        50% = 50% Case
        Below 50% = Below 50% Case
        """
        for record in self:
            percentage = record.actual_deposit_percentage
            if percentage == 100.0:
                record.case_type = '100_percent'
            elif percentage == 50.0:
                record.case_type = '50_percent'
            elif percentage < 50.0:
                record.case_type = 'below_50_percent'
            else:
                # Default for other percentages (e.g., between 50-100)
                record.case_type = '50_percent'

    @api.onchange('date_of_birth')
    def _onchange_date_of_birth(self):
        if self.date_of_birth:
            if self.date_of_birth.year == fields.Date.today().year or self.date_of_birth.year > fields.Date.today().year:
                raise ValidationError(str(f'Invalid Date of Birth...'))

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

        return super(MedicalEquipment, self).create(vals)

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
                'name': product_line.product_id.name,
            }) for product_line in self.medical_equipment_line_ids],
        }
        
        # Create the stock picking
        stock_picking = self.env['stock.picking'].create(picking_vals)  
        stock_picking.action_confirm()
        stock_picking.action_assign()
        stock_picking.button_validate()
        
        # Link the stock picking to your medical equipment record
        self.write({
            'picking_id': stock_picking.id,
            'state': 'validate'  # Or whatever your next state should be
        })
        
        # Optional: Validate the picking automatically
        # stock_picking.button_validate()
        return True
    
    def action_approval(self):
        """
        Handle approval based on case type determined by actual_deposit_percentage.
        100% Case: Single CEO approval → Approved
        50% Case: 2 approval cycles (CEO → CFO) - with remarks required
        Below 50% Case: Sync to welfare portal, then follow 50% case rules with remarks
        Reference Case: 2 approval cycles (CEO → CFO) - no remarks required
        """
        self.ensure_one()
        
        case_type = self.case_type
        current_state = self.state
        
        if case_type == '100_percent':
            # 100%: Single CEO approval → Approved
            self.write({
                'state': 'approved'
            })
            
        elif case_type == '50_percent':
            # 50%: 2 approval cycles with remarks required
            if not self.remarks:
                raise ValidationError('Remarks are required for 50% case type.')
            
            if current_state == 'draft':
                self.write({
                    'state': 'ceo_approval'
                })
            elif current_state == 'ceo_approval':
                self.write({
                    'state': 'approved'
                })
            else:
                raise ValidationError('This record has already been approved.')
                
        elif case_type == 'below_50_percent':
            # Below 50%: Sync to welfare portal first, then remarks required
            if not self.welfare_portal_id:
                raise ValidationError('Welfare Portal ID must be synced before approval for Below 50% cases.')
            
            if not self.welfare_acknowledgment:
                raise ValidationError('Welfare acknowledgment must be received before approval.')
            
            if not self.remarks:
                raise ValidationError('Remarks are required for Below 50% case type.')
            
            if current_state == 'draft':
                self.write({
                    'state': 'ceo_approval'
                })
            elif current_state == 'ceo_approval':
                self.write({
                    'state': 'approved'
                })
            else:
                raise ValidationError('This record has already been approved.')
        
        else:
            # Referral Case or others: 2 approval cycles, no remarks required
            if current_state == 'draft':
                self.write({
                    'state': 'ceo_approval'
                })
            elif current_state == 'ceo_approval':
                self.write({
                    'state': 'approved'
                })
            else:
                raise ValidationError('This record has already been approved.')
        
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
                rec._mark_me_application_synced()
                
                # Step 5: Update record with portal information (like welfare does)
                rec.write({
                    'welfare_portal_id': portal_application_id,
                    'is_synced': True,
                    'last_sync_date': fields.Datetime.now(),
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
    
    def _check_donee_exists_in_portal(self):
        """Check if donee already exists in welfare portal"""
        try:
            endpoint = self.env.company.check_donee_endpoint
            data = {
                "json": {
                    "odooId": self.donee_id.id
                }
            }
            _logger.info(f"Donee checking query parameters: {data}")
            result = self._make_welfare_api_call(endpoint, 'POST', data)
            return result
        except Exception as e:
            _logger.info(f"Donee not found in portal: {str(e)}")
            return None
    
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
    
    def _create_me_portal_application(self):
        """Create medical equipment application in welfare portal"""
        try:
            endpoint = self.env.company.create_application_endpoint
            data = {
                "json": {
                    "applicationData": {
                        "odooId": self.id,
                        "doneeOdooId": self.donee_id.id,
                        "form": {
                            "category": "Medical Equipment",
                            "subcategory": self.case_type,
                            "donee_name": self.donee_id.name,
                            "cnic_no": self.cnic_no,
                            "mobile": self.mobile,
                            "city": self.city,
                            "street": self.street,
                            "date_of_birth": str(self.date_of_birth) if self.date_of_birth else None,
                            "gender": self.gender,
                            "age": self.age,
                            "case_type": self.case_type,
                            "actual_deposit_percentage": self.actual_deposit_percentage,
                            "total_amount": float(self.total_amount),
                            "remarks": self.remarks or ''
                        }
                    }
                }
            }
            result = self._make_welfare_api_call(endpoint, 'POST', data)
            return result
        except Exception as e:
            raise ValidationError(f"Failed to create application in welfare portal: {str(e)}")
    
    def _mark_me_application_synced(self):
        """Mark medical equipment application as synced in welfare portal"""
        try:
            endpoint = self.env.company.mark_application_endpoint
            data = {
                "json": {
                    "odooId": self.id
                }
            }
            result = self._make_welfare_api_call(endpoint, 'POST', data)
            return result
        except Exception as e:
            _logger.error(f"Failed to mark application as synced: {str(e)}")
            return None
    
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
                error_msg = result.get('error', 'Unknown error occurred')
                raise Exception(f"Portal API Error: {error_msg}")
            
            return result.get('json', {})
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"Welfare API Request failed: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
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
            }
        }
    
    def action_acknowledge_welfare_portal(self):
        """
        Mark welfare portal acknowledgment received for Below 50% cases
        """
        self.ensure_one()
        
        if self.case_type != 'below_50_percent':
            raise ValidationError('Only Below 50% cases can receive welfare acknowledgment.')
        
        self.write({'welfare_acknowledgment': True})
        
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
                'default_medical_equipment_id': self.id
            },
            'target': 'new',
        }