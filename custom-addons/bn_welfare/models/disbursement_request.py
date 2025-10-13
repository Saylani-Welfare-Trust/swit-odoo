from odoo import fields, models, api, exceptions, _

from dateutil.relativedelta import relativedelta

import requests
import json
import logging
_logger = logging.getLogger(__name__)



state_selection = [
    ('draft', 'Draft'),
    ('inquiry', 'Inquiry Officer'),
    ('to_approve', 'HOD Approval'),
    ('mem_approve', 'Member Approval'),
    ('approved', 'Approved'),
    # ('waiting_for_approval', 'Waiting For Approval'),
    ('recurring_order', 'Recurring'),
    ('seddisbur', 'Disbursed'),
    ('reject', 'Rejected'),
]

general_selection = [
    ('no', 'No'),
    ('yes', 'Yes'),
]

residence_selection = [
    ('owned', 'Owned'),
    ('shared', 'Shared'),
    ('rented', 'Rented'),
]

kifalat_madad_tenure_selection = [
    ('one_time', 'One Time'),
    ('3M', '3 Months'),
    ('6M', '6 Months'),
    ('1Y', '1 Year'),
    ('3Y', '3 Year'),
    ('other', 'Other'),
]


class DisbursementRequest(models.Model):
    _name = 'disbursement.request'
    _description = 'Disbursement Request'
    _inherit = ["mail.thread", "mail.activity.mixin"]


    donee_id = fields.Many2one('res.partner', string="Donee ID", tracking=True)

    name = fields.Char('Name', tracking=True)
    father_name = fields.Char('Father Name', tracking=True)
    father_cnic = fields.Char('Father CNIC', tracking=True)
    cnic_no = fields.Char(related='donee_id.cnic_no', string='CNIC No.', store=True)

    inquiry_office_id = fields.Many2one('hr.employee', string="Inquiry Officer ID")

    state = fields.Selection(selection=state_selection, string="Status", default="draft", tracking=True)

    disbursement_date = fields.Date('Disbursement Date', default=fields.Date.today(), tracking=True)
    cnic_expiration_date = fields.Date(related='donee_id.cnic_expiration_date', string='CNIC Expiration Date', store=True)

    hod_remarks = fields.Text('HOD Remarks', tracking=True)
    mem_remarks = fields.Text('Member Remarks', tracking=True)

    old_system_record = fields.Char('Old System Record')

    disbursement_request_line_ids = fields.One2many('disbursement.request.line', 'disbursement_request_id', string='Guarator Information IDs')
    guarantor_information_ids = fields.One2many('guarantor.information', 'disbursement_request_id', string='Guarator Information IDs')
    welfare_qualification_ids = fields.One2many('welfare.qualification', 'disbursement_request_id', string="MicroFinance Qualification IDs")
    recurring_disbursement_request_ids = fields.One2many('recurring.disbursement.request', 'disbursement_request_id', string="Recurring Disbursement Request IDs")
    
    # Application Form & FRC / Electricity & Gas Bill & Family CNIC
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

    is_revert = fields.Boolean()
    is_sec_dep_paid = fields.Boolean()

    # Family Members' Detail
    dependent_person = fields.Integer('Number of Dependents', tracking=True)
    household_member = fields.Integer('Household members', tracking=True)
    family_information_ids = fields.One2many('family.information', 'disbursement_request_id', string='Guarator Information IDs')

    # Request Details
    
    tenure_kifalat_madad_expected = fields.Selection(selection=kifalat_madad_tenure_selection, string='Tenure of Kifalat / Madad expected', tracking=True)

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


   


    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('disbursement_request') or _('New')
        return super(DisbursementRequest, self).create(vals)

    def action_to_approve(self):
        # raise exceptions.ValidationError(str('here'))
        
        raise exceptions.ValidationError((str(self.read()), str(self.disbursement_request_line_ids)))
        for line in self.disbursement_request_line_ids:
            if line.order_type == 'recurring':
                if self.env['recurring.disbursement.request'].search_count([('donee_id', '=', self.donee_id.id), ('disbursement_type_id', '=', line.disbursement_type_id.id), ('state', '=', 'draft')]):
                    raise exceptions.ValidationError(f"There are recurring disbursement requests in process for {line.disbursement_type_id.name}. Please complete them first.")

        self.write({'state': 'to_approve'})

    def action_mem_approve(self):
        # raise exceptions.ValidationError(str('here'))
        self.write({'state': 'mem_approve'})

    def action_approved(self):
        self.write({'state': 'approved'})

    def action_rejected(self):
        # raise exceptions.ValidationError((str(self.read()), str(self.disbursement_request_line_ids)))

        if self.state == 'to_approve':
            if not self.hod_remarks:
                raise exceptions.ValidationError('Please provide remarks')
        if self.state == 'mem_approve':
            if not self.mem_remarks:
                raise exceptions.ValidationError('Please provide remarks')
        self.write({'state': 'rejected'})

    def action_revert(self):
        # raise exceptions.ValidationError((str(self.read()), str(self.disbursement_request_line_ids)))


        if self.state == 'to_approve':
            if not self.hod_remarks:
                raise exceptions.ValidationError('Please provide remarks')
            self.is_revert = True
            self.write({'state': 'draft'})
        if self.state == 'mem_approve':
            if not self.mem_remarks:
                raise exceptions.ValidationError('Please provide remarks')
            self.is_revert = True
            self.write({'state': 'to_approve'})

    # def action_proceed(self):
    #     for line in self.disbursement_request_line_ids:
    #         if not line.collection_date:
    #             raise exceptions.ValidationError("Please Enter Collection Date")
        
    #     self.write({
    #         'is_sec_dep_paid': True,
    #         'state': 'waiting_for_approval'
    #     })
    
    def print_disbursement_slip(self):
        raise exceptions.ValidationError(str(self.disbursement_request_line_ids.read()))
        return self.env.ref('bn_welfare.disbursement_slip_report_action').report_action(self)
    
    def action_create_recurring_order(self):
        for line in self.disbursement_request_line_ids:
            if line.order_type != 'recurring':
                raise exceptions.ValidationError('This request does not belong to recurring order')
            
            if line.recurring_duration:
                if line.disbursement_category_id.name != 'Cash':
                    month = 0
                    
                    for i in range(int(line.recurring_duration.split('_')[0])):
                        self.env['recurring.disbursement.request'].create({
                            'disbursement_request_line_id': line.id,
                            'collection_date': line.collection_date + relativedelta(months=month),
                            'disbursement_type_id': line.disbursement_type_id.id,
                            'warehouse_loc_id': line.warehouse_loc_id.id,
                        })

                        month += 1
                else:
                    month = 0
                    
                    for i in range(int(line.recurring_duration.split('_')[0])):
                        self.env['recurring.disbursement.request'].create({
                            'disbursement_request_line_id': line.id,
                            'collection_date': line.collection_date + relativedelta(months=month),
                            'disbursement_type_id': line.disbursement_type_id.id,
                            'warehouse_loc_id': None,
                        })

                        month += 1


        self.state = 'recurring_order'

    def action_disbursed(self):
        for line in self.disbursement_request_line_ids:
            if not line.collection_date:
                raise exceptions.ValidationError('Please enter Collection Date')
            
            # if line.disbursement_category_id.name != 'Cash':
            #     product_quantity = line.product_id.qty_available
            #     if product_quantity > 0:
            #         stock_quant = self.env['stock.quant'].search([
            #             ('location_id', '=', line.warehouse_loc_id.id),
            #             ('product_id', '=',  line.product_id.id),
            #             ('inventory_quantity_auto_apply', '>', 0)
            #         ], limit=1)


            #         if not stock_quant:
            #             raise exceptions.ValidationError('Stock is not available in that location. Kindly select another location')
            #         else:
            #             stock_move = self.env['stock.move'].create({
            #                 'name': f'Decrease stock for Loan {self.name}',
            #                 'product_id': line.product_id.id,
            #                 'product_uom': line.product_id.uom_id.id,
            #                 'product_uom_qty': 1,  # Decrease 1 unit
            #                 'location_id': line.warehouse_loc_id.id,  # Source location (stock)
            #                 'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            #                 'state': 'draft',  # Initial state is draft
            #             })
            #             picking = self.env['stock.picking'].create({
            #                 'partner_id': self.donee_id.id,  # Link to customer
            #                 'picking_type_id': self.env.ref('stock.picking_type_out').id,  # Outgoing picking type
            #                 'move_ids_without_package': [(6, 0, [stock_move.id])],  # Associate the stock move with the picking
            #                 'origin': self.name
            #             })
            #             stock_move._action_confirm()
            #             stock_move._action_assign()
            #             picking.action_confirm()
            #             picking.button_validate()
            #     else:
            #         raise exceptions.ValidationError('Not enough stock available')
            
            move_lines = [
                {
                    'name': f'{self.name}',
                    'account_id': line.product_id.property_account_income_id.id,
                    'credit': line.disbursement_amount,
                    'debit': 0.0,
                    'partner_id': self.donee_id.id,
                    'currency_id': line.currency_id.id if line.currency_id else None,
                },
                {
                    'name': f'{self.name}',
                    'account_id': line.product_id.property_account_expense_id.id,
                    'debit': line.disbursement_amount,
                    'credit': 0.0,
                    'partner_id': self.donee_id.id,
                    'currency_id': line.currency_id.id if line.currency_id else None,
                }
            ]

            move = self.env['account.move'].create({
                'ref': f'{self.name}',
                'partner_id': self.donee_id.id,
                # 'journal_id': journal.id,
                'line_ids': [(0, 0, line) for line in move_lines],
                'date': fields.Date.today(),
                'move_type': 'entry',
            })
            move.action_post()

        self.write({'state': 'disbursed'})


    @api.model
    def check_disbursement_ids(self, data):
        if not data:
            return {
                "status": "error",
                "body": "Please Enter a Disbursement Request No.",
            }

        disbursement_line_ids = self.env['disbursement.request.line'].sudo().search([('disbursement_request_id.name', '=', data), ('disbursement_request_id.state', 'not in', ['disbursed', 'recurring_order']), ('order_type', '!=', 'recurring')])
        if not disbursement_line_ids:
            return {
                "status": "error",
                "body": "Record not found against Request No. "+str(data),
            }

        branch_ids = self.env['res.company'].search([('child_ids', '!=', False)])

        return {
            "status": "success",
            'disbursement_ids': [{
                'id': line.disbursement_request_id.id,
                'name': line.disbursement_request_id.name,
                'donee_name': line.disbursement_request_id.donee_id.name,
                'product': line.product_id.name,
                'disbursement_amount': line.disbursement_amount,
                'collection_point': line.collection_point.title(),
                'currency_id': line.currency_id.id,
                'currency_symbol': line.currency_id.symbol,
                'res_model': 'disbursement.request'
            } for line in disbursement_line_ids],
            'collection_ids':[{'id': branch.id, 'name': branch.name} for branch in branch_ids]
        }
    
    @api.model
    def check_recurring_disbursement_ids(self, data):
        if not data:
            return {
                "status": "error",
                "body": "Please Enter a Disbursement Request No.",
            }

        recurring_disbursement_ids = self.env['recurring.disbursement.request'].sudo().search([('disbursement_request_id.name', '=', data), ('state', '!=', 'disbursed')])
        if not recurring_disbursement_ids:
            return {
                "status": "error",
                "body": "Record not found against Request No. "+str(data),
            }

        branch_ids = self.env['res.company'].search([('child_ids', '!=', False)])

        return {
            "status": "success",
            'disbursement_ids': [{
                    'id': recurring_disbursement_id.id,
                    'name': recurring_disbursement_id.disbursement_request_id.name,
                    'donee_name': recurring_disbursement_id.donee_id.name,
                    'product': recurring_disbursement_id.product_id.name,
                    'disbursement_amount': recurring_disbursement_id.disbursement_amount,
                    'collection_point': recurring_disbursement_id.collection_point,
                    'currency_id': recurring_disbursement_id.currency_id.id,
                    'currency_symbol': recurring_disbursement_id.currency_id.symbol,
                    'res_model': 'recurring.disbursement.request'
                }
                for recurring_disbursement_id in recurring_disbursement_ids
                if recurring_disbursement_id.collection_date.month == fields.Date.today().month
            ],
            'collection_ids':[{'id': branch.id, 'name': branch.name} for branch in branch_ids]
        }
    
    @api.model
    def mark_as_disbursed(self, data):
        # raise exceptions.ValidationError(str(data))
        products_data = []

        if not data:
            return {
                "status": "error",
                "body": "Invalid Disbursement",
            }

        disbursement_id = self.env['disbursement.request.line'].sudo().browse(int(data['disbursement_id']))
        if not disbursement_id:
            return {
                "status": "error",
                "body": "Record not found against Disbursement Number "+str(data['disbursement_number']),
            }
       
        if data['res_model'] == "disbursement.request.line":
             if disbursement_id[0]['collection_point'] != "branch":
                 raise exceptions.ValidationError(str("collection  point is not branch"))

             for line in disbursement_id:
                    product = line.product_id
                    products_data.append({
                        'product_id': product.id,
                        'name': product.name,
                        'price': -line.disbursement_amount,
                        # Add picking type to each product
                    })
        else:
            disbursement_id = self.env['recurring.disbursement.request'].sudo().browse(int(data['disbursement_id']))
            if disbursement_id[0]['collection_point'] != "branch":
                 raise exceptions.ValidationError(str("collection  point is not branch"))

            # disburesmrecurring_disbursement_request_idsent_id = self.env['disbursement.request'].sudo().browse(int(data['disbursement_id']))
            # raise exceptions.ValidationError(str(disbursement_id.read()))
            # disburesment_id.recurring_disbursement_request_ids

            for line in disbursement_id:
                product = line.product_id
                products_data.append({
                    'product_id': product.id,
                    'name': product.name,
                    'price': -line.disbursement_amount,
                    # Add picking type to each product
                })

            
        # raise exceptions.ValidationError(str(products_data))
        partner_id = self.env['res.partner'].search([('id', '=', disbursement_id.donee_id.id)], limit=1)
        

        return {
            'partner_id' : partner_id.id,
            'products' : products_data,
            "report_id": disbursement_id.id,
            "status": "success",
        }


class GuarantorInformation(models.Model):
    _inherit = 'guarantor.information'


    disbursement_request_id = fields.Many2one('disbursement.request', string="Welfare ID")

class WelfareQualification(models.Model):
    _inherit = "welfare.qualification"


    disbursement_request_id = fields.Many2one('disbursement.request', string="Welfare ID")

class FamilyInformation(models.Model):
    _inherit = "family.information"


    disbursement_request_id = fields.Many2one('disbursement.request', string="Welfare ID")
