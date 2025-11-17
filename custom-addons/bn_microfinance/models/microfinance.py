from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import math
import re

from dateutil.relativedelta import relativedelta
from datetime import timedelta

import base64
from io import StringIO, BytesIO
import openpyxl


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
    ('hod_approve', 'HOD Approval'),
    ('mem_approve', 'Member Approval'),
    ('approve', 'Approved'),
    ('wfd', 'Waiting For Delivery'),
    ('in_recovery', 'In Recovery'),
    ('recover', 'Temp Recovered'),
    ('fully_recover', 'Fully Recovered'),
    ('right_granted', 'Right Granted'),
    ('right_of_approval_1', 'Write Off Approval 1'),
    ('right_of_approval_2', 'Write Off Approval 2'),
    ('done', 'Done'),
    ('close', 'Closed'),
    ('reject', 'Rejected'),
]


class Microfinance(models.Model):
    _name = 'microfinance'
    _description = "Microfinance"


    name = fields.Char('Name', default="NEW")
    old_system_record = fields.Char('Old System Record')

    donee_id = fields.Many2one('res.partner', string="Donee")
    product_id = fields.Many2one('product.product', string="Product")
    microfinance_scheme_id = fields.Many2one('microfinance.scheme', string="Microfinance Scheme")
    microfinance_scheme_line_id = fields.Many2one('microfinance.scheme.line', string="Microfinance Scheme Line")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)
    picking_id = fields.Many2one('stock.picking', string="Picking")
    sd_slip_id = fields.Many2one('microfinance.installment', 'SD Slip')
    recovered_location_id = fields.Many2one('stock.location', string="Recovery Location")
    warehouse_location_id = fields.Many2one('stock.location', string="Warehouse Location")
    
    product_domain = fields.Many2many('product.product', string="Product Domain", compute="_compute_product_domain", store=True)
    microfinance_scheme_line_ids = fields.Many2many(
        'microfinance.scheme.line',
        string="Microfinance Scheme Lines",
        compute="_compute_microfinance_scheme_line_ids",
        store=True
    )

    installment_type = fields.Selection(related='microfinance_scheme_id.installment_type', string='Installment Type', store=True)
    asset_type = fields.Selection(related='microfinance_scheme_line_id.asset_type', string='Asset Type', store=True)
    asset_availability = fields.Selection(selection=assest_availability_selection, compute='_compute_asset_availablity', string='Asset Availability')
    state = fields.Selection(selection=state_selection, string='Status', default='draft')

    amount = fields.Monetary('Amount', currency_field='currency_id', default=0)
    security_deposit = fields.Monetary('Security Deposit', currency_field='currency_id', default=0)
    donor_contribution = fields.Monetary('Contribution by Donor', currency_field='currency_id', default=0)
    total_amount = fields.Monetary('Total Amount', compute="_set_total_amount", store=True, currency_field='currency_id')
    installment_amount = fields.Monetary('Installment Amount', compute="_set_installment_amount", store=True, currency_field='currency_id')

    installment_period = fields.Integer('Installment Period',  compute="_set_installment_period", default=1, store=True)

    delivery_date = fields.Date('Delivery Date')

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
    
    pdc_attachment = fields.Binary('PDC')
    pdc_attachment_name = fields.Char('PDC File Name')

    remarks = fields.Text('Remarks')
    hod_remarks = fields.Text('HOD Remarks')
    mem_remarks = fields.Text('Member Remarks')
    cfo_right_of_remarks = fields.Text('CFO Remarks')
    recovery_remarks = fields.Text('Recovery Remarks')
    member_right_of_remarks = fields.Text('Member Remarks')

    in_recovery = fields.Boolean('In Recovery')

    microfinance_line_ids = fields.One2many('microfinance.line', 'microfinance_id', string="Microfinance Lines")
    microfinance_recovery_line_ids = fields.One2many('microfinance.recovery.line', 'microfinance_id', string="Microfinance Recovery Lines")

    # Employee Informaiton Fields
    designation = fields.Char('Designation') 
    company_name = fields.Char('Company Name') 
    company_phone = fields.Char('Company Phone No.') 
    company_address = fields.Char('Company Address')

    service_duration = fields.Integer('Service Duration ( In Years )')

    monthly_salary = fields.Monetary('Monthly Salary', currency_field='currency_id', default=0)

    # Education Information
    educaiton_line_ids = fields.One2many('microfinance.educaiton', 'microfinance_id', string="Educaiton Lines")

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
    guarantor_line_ids = fields.One2many('microfinance.guarantor', 'microfinance_id', string='Guarator Lines')

    # Family Detail
    dependent_person = fields.Integer('No. of Dependents')
    household_member = fields.Integer('Household members')

    family_line_ids = fields.One2many('microfinance.family', 'microfinance_id', string='Family Lines')


    @api.depends('microfinance_scheme_id')
    def _compute_microfinance_scheme_line_ids(self):
        for rec in self:
            if rec.microfinance_scheme_id:
                rec.microfinance_scheme_line_ids = [(6, 0, rec.microfinance_scheme_id.microfinance_scheme_line_ids.ids)]
            else:
                rec.microfinance_scheme_line_ids = [(5, 0, 0)]  # Clear the field if no scheme selected
    
    @api.depends('microfinance_scheme_line_id')
    def _compute_product_domain(self):
        for rec in self:
            rec.product_domain = [(5, 0, 0)]

            if rec.microfinance_scheme_line_id:
                # Fetch lines related to selected scheme line
                lines = self.env['loan.product.line'].search([
                    ('microfinance_scheme_line_id', '=', self.microfinance_scheme_line_id.id)
                ])

                if lines:
                    line_ids = lines.mapped('product_id').ids

                    rec.product_domain = line_ids
                    
                    rec.product_domain = [(6, 0, lines.ids)]

    @api.depends('amount', 'security_deposit', 'donor_contribution')
    def _set_total_amount(self):
        for rec in self:
            rec.total_amount = rec.amount - rec.security_deposit - rec.donor_contribution
    
    @api.depends('product_id')
    def compute_installment_amount(self):
        for rec in self:
            rec.installment_amount = 0

            if rec.product_id:
                record = self.env['loan.product.line'].search([
                    ('microfinance_scheme_line_id', '=', rec.microfinance_scheme_line_id.id),
                    ('product_id', '=', rec.product_id.id)
                ], limit=1)

                if record:
                    rec.installment_amount = record.price
                    rec.security_deposit = record.sd_amount
                else:
                    rec.installment_amount = 0
                    rec.security_deposit = 0

    @api.depends('installment_amount', 'total_amount')
    def _set_installment_period(self):
        for rec in self:
            rec.installment_period = 0

            if rec.installment_amount > 0:
                rec.installment_period = math.ceil(rec.total_amount / rec.installment_amount)
    
    @api.depends('product_id')
    def _compute_asset_availablity(self):
        for rec in self:
            rec.asset_availability = 'not_available'

            if rec.product_id:
                if rec.product_id.qty_available > 0:
                    rec.asset_availability = 'available'


    @api.constrains('landlord_cnic_no')
    def _check_landlord_cnic_format(self):
        for record in self:
            if record.landlord_cnic_no:
                if not re.match(r'^\d{5}-\d{7}-\d{1}$', record.landlord_cnic_no):
                    raise ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.landlord_cnic_no.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")

    @api.onchange('landlord_cnic_no')
    def _onchange_landlord_cnic_no(self):
        if self.landlord_cnic_no:
            cleaned_cnic = re.sub(r'[^0-9]', '', self.cnic_no)
            if len(cleaned_cnic) >= 13:
                self.landlord_cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:12]}-{cleaned_cnic[12:]}"
            elif len(cleaned_cnic) > 5:
                self.landlord_cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:]}"

    def action_move_to_hod(self):
        self.state = 'hod_approve'

    def action_send_to_recovery(self):
        lines = []
        
        for line in self.microfinance_line_ids:
            lines.append((0, 0, {
                'installment_no': line.installment_no,
                'due_date': line.due_date,
                'amount': line.amount,
                'paid_amount': line.paid_amount,
            }))

        self.microfinance_recovery_line_ids = lines

        self.in_recovery = True

        self.state = 'in_recovery'

    def action_move_to_member(self):
        self.state = 'mem_approve'

    def action_reject(self):
        if self.state == 'hod_approve' and not self.hod_remarks:
            raise ValidationError('Please provide HOD Remarks.')
        elif self.state == 'mem_approve' and not self.mem_remarks:
            raise ValidationError('Please provide Member Remarks.')
        
        self.state = 'reject'

    def action_revert(self):
        if self.state == 'hod_approve':
            if not self.hod_remarks:
                raise ValidationError('Please provide HOD Remarks.')
            
            self.state = 'draft'
        elif self.state == 'mem_approve':
            if not self.mem_remarks:
                raise ValidationError('Please provide Member Remarks.')
            
            self.state = 'hod_approve'

    def action_approve(self):
        self.state = 'approve'

    def action_proceed(self):
        if self.asset_type != 'cash' and not self.sd_slip_id:
                raise ValidationError("Please enter Security Deposit Receipt ID")
        elif not self.delivery_date:
            raise ValidationError("Please select a Delivery Date.")
        
        self.state = 'wfd'

    def action_sd_slip(self):
        return self.env.ref('bn_microfinance.security_deposit_report_action').report_action(self)

    def action_move_to_done(self):
        if not self.delivery_date:
            raise ValidationError('Please select a Delivery Date.')
        
        if self.asset_type == 'movable_asset':
            if not self.in_recovery:
                product_quantity = self.product_id.qty_available
                
                if product_quantity > 0:
                    stock_quant = self.env['stock.quant'].search([
                        ('location_id', '=', self.warehouse_location_id.id),
                        ('product_id', '=',  self.product_id.id),
                        ('inventory_quantity_auto_apply', '>', 0)
                    ], limit=1)


                    if not stock_quant:
                        raise ValidationError('The requested stock is unavailable at the moment. Kindly initiate a purchase request to replenish it.')
                    else:
                        stock_move = self.env['stock.move'].create({
                            'name': f'Decrease stock for Loan {self.name}',
                            'product_id': self.product_id.id,
                            'product_uom': self.product_id.uom_id.id,
                            'product_uom_qty': 1,
                            'location_id': self.warehouse_location_id.id,
                            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
                            'state': 'draft',  # Initial state is draft
                        })
                        
                        picking = self.env['stock.picking'].create({
                            'partner_id': self.donee_id.id,
                            'picking_type_id': self.env.ref('stock.picking_type_out').id,
                            'move_ids_without_package': [(6, 0, [stock_move.id])],
                            'origin': self.name
                        })

                        stock_move._action_confirm()
                        stock_move._action_assign()
                        
                        picking.action_confirm()
                        picking.button_validate()
                else:
                    self.asset_availability = 'not_available'

                    raise ValidationError('Not enough stock available.')
            else:
                stock_move = self.env['stock.move'].create({
                    'name': f'Re-Return Product of Loan {self.name}',
                    'product_id': self.recovered_product_id.id,
                    'product_uom': self.recovered_product_id.uom_id.id,
                    'product_uom_qty': 1,  # Decrease 1 unit
                    'location_id': self.recovered_location_id.id,
                    'location_dest_id': self.env.ref('stock.stock_location_customers').id,
                    'state': 'draft',
                })
                picking = self.env['stock.picking'].create({
                    'partner_id': self.customer_id.id,  # Link to customer
                    'picking_type_id': self.env.ref('stock.picking_type_out').id,  # Outgoing picking type
                    'move_ids_without_package': [(6, 0, [stock_move.id])],  # Associate the stock move with the picking
                    'origin': self.name
                })
                stock_move._action_confirm()
                stock_move._action_assign()
                picking.action_confirm()
                picking.button_validate()

        if not self.in_recovery:
            self.compute_installment()
        
        self.state = 'done'

    def action_receipt(self):
        return self.env.ref('bn_microfinance.microfinance_receipt_report_action').report_action(self.sd_slip_id)

    def action_temporary_recovery(self):
        if self.asset_type == 'movable_asset':
            product_line = None

            if self.microfinance_scheme_line_id:
                microfinance_scheme_line = self.env['microfinance.scheme.line'].browse(self.microfinance_scheme_line_id.id)
                product_line = self.env['loan.product.line'].search([
                    ('microfinance_scheme_line_id', '=', microfinance_scheme_line.id),
                    ('product_id', '=', self.product_id.id)
                ], limit=1)

            action = self.env.ref('microfinance_loan.return_microfinance_product_action').read()[0]
            form_view_id = self.env.ref('microfinance_loan.return_microfinance_product_view_form').id
            
            action['views'] = [
                [form_view_id, 'form']
            ]

            if product_line.product_id:
                action['context'] = {
                    'default_donee_id': self.donee_id.id,
                    'default_product_domain': product_line.product_ids.ids,
                    'default_source_document': self.name,
                    'default_microfinance_id': self.id
                }

            return action
        else:
            self.state = 'recover'

    def action_fully_recovered(self):
        self.state = 'fully_recover'

    def action_write_off_request(self):
        if not self.recovery_remarks:
            raise ValidationError('Please provide recovery remarks.')
        
        self.member_right_of_remarks = ''
        self.cfo_right_of_remarks = ''

        self.state = 'right_of_approval_1'

    def action_right_of_approve(self):
        if self.state == 'right_granted':
            self.state = 'right_of_approval_1'
        elif self.state == 'right_of_approval_1':
            self.state = 'right_of_approval_2'
        else:
            self.state = 'right_granted'

    def action_right_of_reject(self):
        if self.state == 'right_of_approval_1':
            if not self.member_right_of_remarks:
                raise ValidationError('Please provide member remarks.')
            
        if self.state == 'right_of_approval_2':
            if not self.cfo_right_of_remarks:
                raise ValidationError('Please provide CFO remarks.')
            
        self.recovery_remarks = ''

        self.state= 'fully_recovered'

    def compute_installment(self):
        if self.installment_amount <= 0 or self.installment_period <= 0 or self.total_amount <= 0:
            return

        self.microfinance_line_ids.unlink()

        total_covered = self.installment_amount * (self.installment_period - 1)
        remaining_amount = max(self.total_amount - total_covered, 0)

        for i in range(self.installment_period):
            if self.installment_type == 'monthly':
                due_date = self.delivery_date + relativedelta(months=i + 1)
            elif self.installment_type == 'daily':
                due_date = self.delivery_date + timedelta(days=i + 1)

            if i < self.installment_period - 1:
                amount = self.installment_amount
            else:
                amount = remaining_amount

            self.env['microfinance.line'].create({
                'microfinance_id': self.id,
                'installment_no': f"{self.name}/{i + 1:04d}",
                'due_date': due_date,
                'paid_amount': 0,
                'amount': amount
            })

    def download_pdc_template(self):
        return self.env.ref('bn_microfinance.microfinance_pdc_template_report_action').report_action(self)
    
    def action_upload_cheques(self):
        if not self.pdc_attachment:
            raise ValidationError("Please Upload PDC file.")
        
        # Ensure the file is uploaded and has the correct extension
        if not self.pdc_attachment_name.lower().endswith('.xlsx'):
            raise ValidationError("Please upload a valid .xlsx file.")

        file_content = base64.b64decode(self.pdc_attachment)
        xlsx_file = BytesIO(file_content)

        try:
            workbook = openpyxl.load_workbook(xlsx_file, data_only=True)
        except Exception as e:
            raise ValidationError(f"Error opening the Excel file: {e}")

        sheet = workbook.active

        # Read the XLSX data
        for row in sheet.iter_rows(min_row=2, values_only=True):  # Start reading from the second row
            if not row:
                continue

            microfinance_line_id = row[0]
            cheque_number = row[1]
            bank_name = row[2]
            cheque_date = row[3]

            line = self.microfinance_line_ids.browse(microfinance_line_id)

            line.write({
                'cheque_no': cheque_number,
                'bank_name': bank_name,
                'cheque_date': cheque_date,
            })

    @api.model
    def create(self, vals):
        if vals.get('name', _('NEW')) == _('NEW'):
            sequence_code = f"microfinance.{vals.get('microfinance_scheme_id')}"
            
            vals['name'] = "MF/"
            vals['name'] += self.env['ir.sequence'].next_by_code(sequence_code) or _('New')
        
        return super(Microfinance, self).create(vals)