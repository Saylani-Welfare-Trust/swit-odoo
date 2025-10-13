from email.policy import default

from odoo import fields, api, models,_
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
from datetime import date
from datetime import timedelta
import base64
from io import StringIO, BytesIO
import openpyxl
import math
from datetime import datetime, timedelta


general_selection = [
    ('no', 'No'),
    ('yes', 'Yes'),
]

residence_selection = [
    ('owned', 'Owned'),
    ('shared', 'Shared'),
    ('rented', 'Rented'),
]

loan_tenure_selection = [
    ('12M', '12 Months'),
    ('24M', '24 Months'),
    ('36M', '36 Months'),
    ('other', 'Other'),
]


class MfdLoanRequest(models.Model):
    _name = 'mfd.loan.request'
    _description = 'Microfinance Loan Request'

    name = fields.Char(string="Name", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    scheme_id = fields.Many2one('mfd.scheme', string='Scheme')
    application_id = fields.Many2one('mfd.scheme.line', string='Application For')
    application_ids_domain = fields.Many2many('mfd.scheme.line', string='Application Id Domain')

    asset_type = fields.Selection([('cash', 'Cash'), ('movable_asset', 'Movable Asset'), ('immovable_asset', 'Immovable Asset')], string='Asset Type', default='cash')
    customer_id = fields.Many2one('res.partner', 'Customer')
    cnic = fields.Char(string='CNIC', related='customer_id.cnic_no')
    is_employee = fields.Boolean(string='Is Employee', related='customer_id.is_employee')
    product_id = fields.Many2one('product.product', string='Asset')
    product_ids_domain = fields.Many2many('product.product', string='Product Domain')

    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)
    amount = fields.Monetary('Amount', currency_field='currency_id')
    security_deposit = fields.Monetary('Security Deposit', currency_field='currency_id', default=0)
    donor_contribution = fields.Monetary('Contribution by Donor', currency_field='currency_id', default=0)
    total_amount = fields.Monetary('Total Amount', currency_field='currency_id')
    disbursement_date = fields.Date('Delivery Date')
    installment_type = fields.Selection([('daily', 'Daily'), ('monthly', 'Monthly')], string='Installment Type', default='daily')
    installment_amount = fields.Monetary('Installment Amount', currency_field='currency_id')
    installment_period = fields.Integer('Installment Period', default=1, help="Total duration of the installment plan in months")
    asset_availability = fields.Selection([('not_available', 'Not Available'), ('available', 'Available')], compute='_compute_asset_availablity', string='Asset Availability')
    warehouse_loc_id = fields.Many2one('stock.location', 'Warehouse/Location')
    loan_reqeust_lines = fields.One2many('mfd.loan.request.line', 'loan_request_id')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'HOD Approval'),
        ('mem_approve', 'Member Approval'),
        ('approved', 'Approved'),
        ('waiting_delivery', 'Waiting For Delivery'),
        ('done', 'Done'),
        ('paid', 'Closed'),
        ('rejected', 'Rejected'),
        ('in_recovery', 'In Recovery'),
        ('recovered', 'Temp Recovered'),
        ('fully_recovered', 'Fully Recovered'),
        ('right_of_approval', 'Write Off Approval 1'),
        ('right_of_approval_2', 'Write Off Approval 2'),
        ('right_of_granted', 'Right of Granted')],
        string='Status',
        default='draft', copy=False, index=True, readonly=True,
        store=True, tracking=True)

    attachment_id = fields.Binary(string="Application Form")
    attachment_name = fields.Char()
    frc_id = fields.Binary(string="FRC")
    frc_name = fields.Char()
    electricity_bill_id = fields.Binary(string="Electricity Bill")
    electricity_bill_name = fields.Char()
    gas_bill_id = fields.Binary(string="Gas Bill")
    gas_bill_name = fields.Char()
    family_cnic_id = fields.Binary(string="Family CNIC")
    family_cnic_name = fields.Char()
    hod_remarks = fields.Html(string="HOD Remarks")
    mem_remarks = fields.Html(string="Member Remarks")
    initiate_recovery = fields.Boolean()
    remaining_amount = fields.Monetary('Remaining Amount', currency_field='currency_id', compute='_compute_amount')
    paid_amount = fields.Monetary('Paid Amount', currency_field='currency_id', compute='_compute_amount')
    installment_paid_amount = fields.Monetary('Paid Amount', currency_field='currency_id')

    recovered_location_id = fields.Many2one('stock.location', 'Destination Location')
    remarks = fields.Html(string='Remarks')
    member_right_of_remarks = fields.Html(string='Member Remarks')

    pdc_attachment_id = fields.Binary(string="Attach PDCs")
    pdc_attachment_name = fields.Char()
    is_revert = fields.Boolean()
    is_sec_dep_paid = fields.Boolean()
    sd_slip_id = fields.Many2one('mfd.installment.receipt', 'SD Slip')
    recovery_id = fields.Many2one('mfd.recovery', 'Recovery ID')

    # Syed Owais Noor

    old_system_record = fields.Char('Old System Record')

    # Syed Owais Noor

    # Guarantor Information

    # Person 1
    person1_name = fields.Char(string='Name')
    person1_cnic = fields.Char(string='CNIC')
    person1_address = fields.Char(string='Address')
    person1_phone = fields.Char(string='Phone No')
    person1_occupation = fields.Char(string='Occupation')
    person1_relation = fields.Char(string='Relation')
    person1_attachment_id = fields.Binary(string="Attach CNIC")
    person1_attachment_name = fields.Char()
    # Person 2
    person2_name = fields.Char(string='Name')
    person2_cnic = fields.Char(string='CNIC')
    person2_address = fields.Char(string='Address')
    person2_phone = fields.Char(string='Phone No')
    person2_occupation = fields.Char(string='Occupation')
    person2_relation = fields.Char(string='Relation')
    person2_attachment_id = fields.Binary(string="Attach CNIC")
    person2_attachment_name = fields.Char()
    # Person 3
    person3_name = fields.Char(string='Name')
    person3_cnic = fields.Char(string='CNIC')
    person3_address = fields.Char(string='Address')
    person3_phone = fields.Char(string='Phone No')
    person3_occupation = fields.Char(string='Occupation')
    person3_relation = fields.Char(string='Relation')
    person3_attachment_id = fields.Binary(string="Attach CNIC")
    person3_attachment_name = fields.Char()

    guarantor_information_ids = fields.One2many('guarantor.information', 'microfinance_id', string='Guarator Information IDs')
    microfinance_qualification_ids = fields.One2many('microfinance.qualification', 'microfinance_id', string="MicroFinance Qualification IDs")
    
    # House Ownership / Residency Details
    residence_type = fields.Selection(selection=residence_selection, string="Residence Type", tracking=True)

    home_phone_no = fields.Char('Home Phone No.', tracking=True)
    cnic_no_landlord = fields.Char('CNIC No. of Landlord', tracking=True)
    mobile_no_landlord = fields.Char('Mobile No. of Landlord', tracking=True)
    landlord_owner = fields.Char('Name of Landlord / Owner', tracking=True)
    rental_shared_duration = fields.Char('Rental / Shared Duration', tracking=True)
    
    per_month_rent = fields.Float('Per month Rent', tracking=True)
    gas_bill = fields.Float('Cumulative Gas Bill of 6 Months (Total)', tracking=True)
    electricity_bill = fields.Float('Cumulative Electricity Bill of 6 Months (total)', tracking=True)
    
    home_other_info = fields.Text('Other info / Addres of Landlord', tracking=True)

    # Family Members' Detail
    dependent_person = fields.Integer('Number of Dependents', tracking=True)
    household_member = fields.Integer('Household members', tracking=True)
    family_information_ids = fields.One2many('family.information', 'microfinance_id', string='Guarator Information IDs')

    # Request Details
    loan_request_amount = fields.Float('Loan Request Amount', tracking=True)
    
    loan_tenure_expected = fields.Selection(selection=loan_tenure_selection, string='Loan Tenure Expected', tracking=True)

    security_offered = fields.Char('Security Offered', tracking=True)

    # Other Information
    aid_from_other_organization = fields.Selection(selection=general_selection, string="Aid from Other Organisation", tracking=True)
    have_applied_swit = fields.Selection(selection=general_selection, string="Have you ever applied with SWIT?", tracking=True)

    details_1 = fields.Text('Details 1', tracking=True)
    details_2 = fields.Text('Details 2', tracking=True)
    
    driving_license = fields.Selection(selection=general_selection, string="Driving License", tracking=True)

    # Other Financial Information
    monthly_income = fields.Float('Monthly Income', tracking=True)
    outstanding_amount = fields.Float('Outstanding Amount', tracking=True)
    monthly_household_expense = fields.Float('Monthly Household Expenses', tracking=True)
    
    bank_account = fields.Selection(selection=general_selection, string="Bank Account", tracking=True)
    
    bank_name = fields.Char('Bank Name', tracking=True)
    account_no = fields.Char('Account No', tracking=True)
    institute_name = fields.Char('Institution Name', tracking=True)

    other_loan = fields.Selection(selection=general_selection, string="Any Other Loan?", tracking=True)

    # Employment Details
    company_name = fields.Char('Company Name', tracking=True)
    company_address = fields.Char('Company Address', tracking=True)
    company_phone_no = fields.Char('Company Phone No.', tracking=True)
    designation = fields.Char('Designation', tracking=True)
    duration_of_service = fields.Char('Duration of service (in years)', tracking=True)

    monthly_salary = fields.Float('Monthly Salary', tracking=True)

    def _compute_amount(self):
        for rec in self:
            installment_ids = self.env['mfd.loan.request.line'].search([
                ('loan_request_id', '=', rec.id)
            ])
            unpaid_filtered_installments = installment_ids.filtered(lambda r: r.state != 'paid')
            total_remaining_amount = sum(unpaid_filtered_installments.mapped('remaining_amount'))

            paid_filtered_installments = installment_ids.filtered(lambda r: r.state in ('paid','partial'))
            total_paid_amount = sum(paid_filtered_installments.mapped('paid_amount'))

            rec.remaining_amount = total_remaining_amount
            rec.paid_amount = total_paid_amount


    def compute_recovery_doc(self):

        # recovery_days_daily = self.env.ref('microfinance_loan.installment_type_daily').days
        # recovery_days_monthly = self.env.ref('microfinance_loan.installment_type_monthly').days

        loan_requests = self.env['mfd.loan.request'].search([
            ('state', '=', 'done')
        ])
        for loan_request in loan_requests:
            if loan_request.installment_type == 'monthly':
                days = loan_request.scheme_id.monthly_recovery_days
            else:
                days = loan_request.scheme_id.daily_recovery_days
            overdue_unpaid_count = False
            for line in loan_request.loan_reqeust_lines:
                if line.state == 'unpaid' and line.due_date < date.today() - timedelta(days=days):
                    overdue_unpaid_count = True
                    break

            loan_request.write({'initiate_recovery': overdue_unpaid_count})


    @api.onchange('scheme_id')
    def compute_application_id_domain(self):
        self.application_id = False
        if self.scheme_id:
            self.installment_type = self.scheme_id.installment_type
            self.application_ids_domain = self.env['mfd.scheme.line'].search([
                ('scheme_id', '=', self.scheme_id.id)
            ])
        else:
            self.application_ids_domain = False

    @api.onchange('application_id')
    def compute_asset_type(self):
        if self.application_id:
            self.asset_type = self.application_id.asset_type
        else:
            self.asset_type = 'cash'


    @api.onchange('scheme_id','application_id')
    def compute_product_id_domain(self):
        self.product_id = False
        if self.application_id:
            records = self.env['loan.product.line'].search([
                ('application_id', '=', self.application_id.id)
            ])
            if records:
                product_ids = records.mapped('product_id').ids
                self.product_ids_domain = product_ids
            else:
                self.product_ids_domain = False
        else:
            self.product_ids_domain = False

    @api.onchange('product_id')
    def compute_installment_amount(self):
        self.installment_amount = 0
        if self.product_id:
            record = self.env['loan.product.line'].search([
                ('application_id', '=', self.application_id.id),
                ('product_id', '=', self.product_id.id)
            ], limit=1)
            if record:
                self.installment_amount = record.price
                self.security_deposit = record.sd_amount
            else:
                self.installment_amount = False
                self.security_deposit = False
        else:
            self.installment_amount = False
            self.security_deposit = False


    @api.onchange('installment_amount', 'total_amount')
    def onchange_installment_amount(self):
        if self.installment_amount > 0:
            self.installment_period = math.ceil(self.total_amount / self.installment_amount)
        else:
            self.installment_period = 0

    @api.onchange('security_deposit', 'amount', 'donor_contribution')
    def onchange_amount_security_dep(self):
        self.total_amount = self.amount - self.security_deposit - self.donor_contribution

    def _compute_asset_availablity(self):
        if self.product_id:
            available_qty = self.product_id.qty_available
            if available_qty > 0:
                self.asset_availability = 'available'
            else:
                self.asset_availability = 'not_available'
        else:
            self.asset_availability = 'not_available'

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            sequence_code = f"mfd.loan.request.{vals.get('scheme_id')}"
            vals['name'] = "MF:"
            vals['name'] += self.env['ir.sequence'].next_by_code(sequence_code) or _('New')
        record = super().create(vals)
        return record


    @api.onchange('product_id')
    def onchange_product(self):
        self.amount = self.product_id.lst_price

        available_qty = self.product_id.qty_available

        if available_qty > 0:
            self.asset_availability = 'available'
        else:
            self.asset_availability = 'not_available'

    def action_to_approve(self):
        # if self.asset_type == 'asset' and self.asset_availability == 'not_available':
        #     raise UserError('Asset is not Available')
        # else:
        self.write({'state': 'to_approve'})

    def action_mem_approve(self):
        self.write({'state': 'mem_approve'})

    def action_approved(self):
        self.write({'state': 'approved'})

    def action_done(self):
        if not self.disbursement_date:
            raise UserError('Please enter Disbursement Date')
        if self.asset_type == 'movable_asset':
            product_quantity = self.product_id.qty_available
            if product_quantity > 0:
                stock_quant = self.env['stock.quant'].search([
                    ('location_id', '=', self.warehouse_loc_id.id),
                    ('product_id', '=',  self.product_id.id),
                    ('inventory_quantity_auto_apply', '>', 0)
                ], limit=1)


                if not stock_quant:
                    raise UserError('Stock is not available in that location. Kindly select another location')
                else:
                    stock_move = self.env['stock.move'].create({
                        'name': f'Decrease stock for Loan {self.name}',
                        'product_id': self.product_id.id,
                        'product_uom': self.product_id.uom_id.id,
                        'product_uom_qty': 1,  # Decrease 1 unit
                        'location_id': self.warehouse_loc_id.id,  # Source location (stock)
                        'location_dest_id': self.env.ref('stock.stock_location_customers').id,
                        'state': 'draft',  # Initial state is draft
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

            else:
                self.write({'asset_availability': 'not_available'})
                raise UserError('Not enough stock available')

        # journal = self.env['account.journal'].search([('name', '=', 'MicroFinance Loan')], limit=1)
        if self.asset_type == 'movable_asset':
            sec_dep_credit_account = self.env.ref('microfinance_loan.security_deposit_credit_account_asset').account_id
            sec_dep_debit_account = self.env.ref('microfinance_loan.security_deposit_debit_account_asset').account_id
        else:
            sec_dep_credit_account = self.env.ref('microfinance_loan.security_deposit_credit_account_cash').account_id
            sec_dep_debit_account = self.env.ref('microfinance_loan.security_deposit_debit_account_cash').account_id


        if not sec_dep_credit_account:
            raise UserError('No Credit Account found')
        if not sec_dep_debit_account:
            raise UserError('No Debit Account found')
        # if not journal:
        #     raise UserError('No Credit Account found')

        move_lines = [
            {
                'name': f'{self.name}',
                'account_id': sec_dep_credit_account.id,
                'credit': self.security_deposit,
                'debit': 0.0,
                'partner_id': self.customer_id.id,
                'currency_id': self.currency_id.id if self.currency_id else None,
            },
            {
                'name': f'{self.name}',
                'account_id': sec_dep_debit_account.id,
                'debit': self.security_deposit,
                'credit': 0.0,
                'partner_id': self.customer_id.id,
                'currency_id': self.currency_id.id if self.currency_id else None,
            }
        ]

        move = self.env['account.move'].create({
            'ref': f'{self.name}',
            'partner_id': self.customer_id.id,
            # 'journal_id': journal.id,
            'line_ids': [(0, 0, line) for line in move_lines],
            'date': fields.Date.today(),
            'move_type': 'entry',
        })
        move.action_post()

        if self.asset_type == 'movable_asset':
            asset_credit_account = self.env.ref('microfinance_loan.loan_asset_credit_account_asset').account_id
            donor_contribution_credit_account = self.env.ref('microfinance_loan.loan_donor_contribution_credit_account_asset').account_id
            income_credit_account = self.env.ref('microfinance_loan.loan_income_credit_account_asset').account_id
            loan_debit_account = self.env.ref('microfinance_loan.loan_debit_account_asset').account_id

            if not asset_credit_account:
                raise UserError('No Loan Asset Credit Account found')
            if not donor_contribution_credit_account:
                raise UserError('No Donor Contribution Credit Account found')
            if not income_credit_account:
                raise UserError('No Loan Income Credit Account found')
            if not loan_debit_account:
                raise UserError('No Loan Debit Account found')

            asset_amount = self.product_id.lst_price
            income_amount = self.amount - asset_amount

            move_lines = [
                {
                    'name': f'{self.name}',
                    'account_id': asset_credit_account.id,
                    'credit': self.total_amount,
                    'debit': 0.0,
                    'partner_id': self.customer_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                },
                {
                    'name': f'{self.name}',
                    'account_id': donor_contribution_credit_account.id,
                    'credit': self.donor_contribution,
                    'debit': 0.0,
                    'partner_id': self.customer_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                },
                {
                    'name': f'{self.name}',
                    'account_id': income_credit_account.id,
                    'credit': self.security_deposit,
                    'debit': 0.0,
                    'partner_id': self.customer_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                },
                {
                    'name': f'{self.name}',
                    'account_id': loan_debit_account.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': self.customer_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                }
            ]
        else:
            loan_credit_account = self.env.ref('microfinance_loan.loan_credit_account_cash').account_id
            loan_debit_account = self.env.ref('microfinance_loan.loan_debit_account_cash').account_id

            if not loan_credit_account:
                raise UserError('No Loan Income Credit Account found')
            if not loan_debit_account:
                raise UserError('No Loan Debit Account found')

            move_lines = [
                {
                    'name': f'{self.name}',
                    'account_id': loan_credit_account.id,
                    'credit': self.total_amount,
                    'debit': 0.0,
                    'partner_id': self.customer_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                },
                {
                    'name': f'{self.name}',
                    'account_id': loan_debit_account.id,
                    'debit': self.total_amount,
                    'credit': 0.0,
                    'partner_id': self.customer_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                }
            ]


        move = self.env['account.move'].create({
            'ref': f'{self.name}',
            'partner_id': self.customer_id.id,
            # 'journal_id': journal.id,
            'line_ids': [(0, 0, line) for line in move_lines],
            'date': fields.Date.today(),
            'move_type': 'entry',
        })

        move.action_post()
        self.compute_installment()
        self.write({'state': 'done'})


    def action_rejected(self):
        if self.state == 'to_approve':
            if not self.hod_remarks:
                raise UserError('Please provide remarks')
        if self.state == 'mem_approve':
            if not self.mem_remarks:
                raise UserError('Please provide remarks')
        self.write({'state': 'rejected'})

    def action_in_recovery(self):
        lines = []
        for line in self.loan_reqeust_lines:
            lines.append(
                (0, 0, {
                    'installment_number': line.installment_number,
                    'installment_id': line.installment_id,
                    'due_date': line.due_date,
                    'amount': line.amount,
                    'paid_amount': line.paid_amount,
                })
            )
        if self.recovery_id:
            self.recovery_id.unlink()
            # self.recovery_id.write({
            #     'loan_id': self.id,
            #     'state': 'in_recovery',
            #     'attachment_id': self.attachment_id,
            #     'attachment_name': self.attachment_name,
            #     'recovery_request_lines': lines,
            # })
        # else:
        recovery_record = self.env['mfd.recovery'].create({
            'loan_id': self.id,
            'state': 'in_recovery',
            'attachment_id': self.attachment_id,
            'attachment_name': self.attachment_name,
            'recovery_request_lines': lines,
        })
        self.write({'recovery_id': recovery_record.id})
        self.write({'state': 'in_recovery'})


    def action_recovered(self):
        if self.asset_type == 'movable_asset':
            if self.application_id:
                application = self.env['mfd.scheme.line'].browse(self.application_id.id)
                product_line = self.env['loan.product.line'].search([
                    ('application_id', '=', application.id),
                    ('product_id', '=', self.product_id.id)
                ], limit=1)

            action = self.env.ref('microfinance_loan.act_mfd_stock_return_picking').read()[0]
            form_view_id = self.env.ref('microfinance_loan.view_mfd_stock_return_picking_form').id
            action['views'] = [
                [form_view_id, 'form']
            ]
            if product_line.recover_product_id:
                action['context'] = {
                    'default_product_id': product_line.recover_product_id.id,
                    'default_partner_id': self.customer_id.id,
                    'default_source_document': self.name,
                    'default_loan_id': self.id
                }
            return action
        else:
            self.write({'state': 'recovered'})

    def compute_installment(self):
        if self.installment_amount <= 0 or self.installment_period <= 0 or self.total_amount <= 0:
            return False

        self.loan_reqeust_lines.unlink()
        total_covered = self.installment_amount * (self.installment_period - 1)
        remaining_amount = max(self.total_amount - total_covered, 0)

        for i in range(self.installment_period):
            if self.installment_type == 'monthly':
                due_date = self.disbursement_date + relativedelta(months=i + 1)
            elif self.installment_type == 'daily':
                due_date = self.disbursement_date + timedelta(days=i + 1)

            if i < self.installment_period - 1:
                amount = self.installment_amount
            else:
                amount = remaining_amount

            self.env['mfd.loan.request.line'].create({
                'loan_request_id': self.id,
                'installment_number': i + 1,
                'installment_id': f"{self.name}/00{i + 1}",
                'due_date': due_date,
                'paid_amount': 0,
                'amount': amount,
                'cheque_amount': amount
            })

    def upload_cheques(self):
        if not self.pdc_attachment_id:
            raise UserError("Please Upload PDC file.")
        # Ensure the file is uploaded and has the correct extension
        if not self.pdc_attachment_name.lower().endswith('.xlsx'):
            raise UserError("Please upload a valid .xlsx file.")

        file_content = base64.b64decode(self.pdc_attachment_id)
        xlsx_file = BytesIO(file_content)

        try:
            workbook = openpyxl.load_workbook(xlsx_file, data_only=True)
        except Exception as e:
            raise UserError(f"Error opening the Excel file: {e}")

        sheet = workbook.active

        # Read the XLSX data
        for row in sheet.iter_rows(min_row=2, values_only=True):  # Start reading from the second row
            if not row:
                continue

            installment_id = row[0]
            cheque_number = row[1]
            bank_name = row[2]
            cheque_amount = row[3]
            cheque_date = row[4]

            line = self.loan_reqeust_lines.search([
                ('installment_id', '=', installment_id)
            ])
            bank_id = self.env['mfd.bank'].search([
                ('name', '=', bank_name)
            ])
            line.write({
                'cheque_no': cheque_number,
                'mfd_bank_id': bank_id,
                'cheque_amount': cheque_amount,
                'cheque_date': cheque_date,
            })

    def download_pdc_template(self):
        return self.env.ref('microfinance_loan.report_mfd_pdc_template').report_action(self)

    def action_right_of_approval(self):
        if not self.remarks:
            raise UserError('Please provide remarks')
        self.write({'state': 'right_of_approval'})

    def action_right_of_granted(self):
        self.write({'state': 'right_of_granted'})

    def action_right_of_rejected(self):
        if not self.member_right_of_remarks:
            raise UserError('Please provide remarks')
        self.write({'state': 'in_recovery'})

    def action_revert(self):
        if self.state == 'to_approve':
            if not self.hod_remarks:
                raise UserError('Please provide remarks')
            self.is_revert = True
            self.write({'state': 'draft'})
        if self.state == 'mem_approve':
            if not self.mem_remarks:
                raise UserError('Please provide remarks')
            self.is_revert = True
            self.write({'state': 'to_approve'})

    def action_proceed(self):
        if self.asset_type != 'cash':
            if not self.sd_slip_id:
                raise UserError("Please enter Security Deposit Receipt ID")
        if not self.disbursement_date:
            raise UserError("Please enter Delivery Date")
        self.write({
            'is_sec_dep_paid': True,
            'state': 'waiting_delivery'
        })

    def print_sd_slip(self):
        return self.env.ref('microfinance_loan.report_security_deposit_slip').report_action(self)

    def print_mfd_slip(self):
        return self.env.ref('microfinance_loan.report_mfd_slip').report_action(self)


class GuarantorInformation(models.Model):
    _inherit = 'guarantor.information'


    microfinance_id = fields.Many2one('mfd.loan.request', string="MicroFinance ID")

class MicrofinanceQualification(models.Model):
    _inherit = "microfinance.qualification"


    microfinance_id = fields.Many2one('mfd.loan.request', string="MicroFinance ID")

class MicrofinanceQualification(models.Model):
    _inherit = "family.information"


    microfinance_id = fields.Many2one('mfd.loan.request', string="MicroFinance ID")