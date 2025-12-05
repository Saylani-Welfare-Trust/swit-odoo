from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import re

# CNIC regular expression
cnic_pattern = r'^\d{5}-\d{7}-\d{1}$'

status_selection = [       
    ('draft', 'Draft'),
    ('payment_received', 'Payment Received'),
    ('validate', 'Validate'),
    ('return', 'Return'),
    ('payment_return','Payment Return'),
]


class MedicalEquipment(models.Model):
    _name = 'medical.equipment'
    _description = "Medical Equipment"


    donee_id = fields.Many2one('res.partner', string="Donee")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    picking_id = fields.Many2one('stock.picking', string="Picking")
    return_picking_id = fields.Many2one('stock.picking', string="Return Picking")

    name = fields.Char('Name', default="New")
    country_code_id = fields.Many2one(related='donee_id.country_code_id', string="Country Code", store=True)
    mobile = fields.Char(related='donee_id.mobile', string="Mobile No.", store=True, size=10)
    city = fields.Char(related='donee_id.city', string="City", store=True)
    street = fields.Char(related='donee_id.street', string="Street", store=True)
    cnic_no = fields.Char(related='donee_id.cnic_no', string="CNIC No.", store=True, size=13)

    date_of_birth = fields.Date(related='donee_id.date_of_birth', string="Date of Birth", store=True)

    age = fields.Integer('Age',compute="_compute_age", store=True)

    gender = fields.Selection(related='donee_id.gender', string="Gender", store=True)
    state = fields.Selection(selection=status_selection, string="Status", default="draft")
    
    total_amount = fields.Monetary('Total Amount', currency_field='currency_id',compute='_compute_total_amount',store=True)
    service_charges = fields.Monetary('Service Charges', currency_field='currency_id')

    is_donee_register = fields.Boolean('Is Donee Register', compute="_set_is_donee_register", store=True)

    medical_equipment_line_ids = fields.One2many('medical.equipment.line', 'medical_equipment_id', string="Medical Equipments")


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

    def is_valid_cnic_characters(cnic):
        """Return True only if CNIC contains digits and '-' only."""
        return bool(re.fullmatch(r'[0-9-]*', cnic))

    @api.onchange('cnic_no')
    def _onchange_cnic_no(self):
        if self.cnic_no:
            cleaned_cnic = re.sub(r'[^0-9]', '', self.cnic_no)
            if len(cleaned_cnic) >= 13:
                self.cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:12]}-{cleaned_cnic[12:]}"
            elif len(cleaned_cnic) > 5:
                self.cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:]}"

            if not self.is_valid_cnic_characters(self.cnic_no):
                raise ValidationError('Invalid CNIC No. Can contain only digit and -')
    
    @api.depends('medical_equipment_line_ids.amounts', 'medical_equipment_line_ids.quantity')
    def _compute_total_amount(self):
        for record in self:
            total = 0.0
            for line in record.medical_equipment_line_ids:
                # Use 'amount' instead of 'amounts'
                total += line.amounts * line.quantity
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

            line.amount = total_price_incl_tax * line.quantity

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