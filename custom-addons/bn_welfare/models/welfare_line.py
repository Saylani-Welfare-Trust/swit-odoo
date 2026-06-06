from odoo import models, fields,_,api
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

collection_point_selection = [
    ('bank', 'Bank'),
    ('branch', 'Branch'),
]

order_type_selection = [
    ('one_time', 'One Time'),
    ('recurring', 'Recurring'),
    ('both', 'Both'),
]

payment_type_selection = [
    ('self', 'Self'),
    ('assigned_officer', 'Assigned Officer (Marfat)'),
]

state_selection = [
    ('draft', 'Draft'),
    ('delivered', 'Delivery Created'),
    ('disbursed', 'Disbursed'),
    ('pending', 'Pending'),
    ('collected', 'Collected'),
    ('return', 'Returned'),  
]

recurring_duration_selection = [
    ('3_M', '3 Months'),
    ('4_M', '4 Months'),
    ('5_M', '5 Months'),
    ('6_M', '6 Months'),
    ('7_M', '7 Months'),
    ('8_M', '8 Months'),
    ('9_M', '9 Months'),
    ('10_M', '10 Months'),
    ('11_M', '11 Months'),
    ('12_M', '12 Months'),
]


class WelfareLine(models.Model):
    _name = 'welfare.line'
    _description = "Welfare Line"

    return_date = fields.Datetime('Return Date', readonly=True)
    return_bill_id = fields.Many2one('account.move', string='Return Bill', readonly=True)
    pos_return_order_id = fields.Many2one('pos.order', string='POS Return Order', readonly=True)
    return_reason = fields.Text('Return Reason')
    returned_by = fields.Many2one('res.users', string='Returned By', default=lambda self: self.env.user)


    product_domain = fields.Char('Product Domain', compute='_compute_product_domain', default="[]", store=True)
    analytic_account_domain = fields.Char('Analytic Account Domain', compute='_compute_analytic_account_domain', default="[]", store=True)
    employee_category_id_officer = fields.Many2one(
        'hr.employee.category', 
        string="Employee Category", 
        default=lambda self: self.env.ref('bn_welfare.assigned_officer_hr_employee_category', raise_if_not_found=False).id if self.env.ref('bn_welfare.assigned_officer_hr_employee_category', raise_if_not_found=False) else False
    )
    # order_type field moved to main welfare model
    collection_point = fields.Selection(selection=collection_point_selection, string="Collection Point" )
    payment_type = fields.Selection(selection=payment_type_selection, string="Payment Type", default='self')
    assigned_officer_id = fields.Many2one('hr.employee', string="Assigned Officer (Marfat)", domain="[('category_ids', 'in', [employee_category_id_officer])]")
    recurring_duration = fields.Selection(selection=recurring_duration_selection, string="Recurring Duration")
    state = fields.Selection(selection=state_selection, string="State", default='draft')

    welfare_id = fields.Many2one('welfare', string="Welfare")
    product_id = fields.Many2one('product.product', string="Product")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Branch")
    disbursement_category_id = fields.Many2one('disbursement.category', string="Disbursement Category")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    disbursement_application_type_id = fields.Many2one('disbursement.application.type', string="Disbursement Application Type")
    # warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse")
    # warehouse_domain = fields.Char('Warehouse Domain', compute='_compute_warehouse_domain', default="[]", store=True)
    bill_id = fields.Many2one('account.move', string="Bill", readonly=True)
    # net_amount = fields.Float(
    #     'Net Amount',
    #     compute='_compute_net_amount',
    #     store=True
    # )

    # manual_net_total = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    fixed_amount_check = fields.Boolean('Fixed Amount Check', default=False, compute='_compute_fixed_amount_check')
    show_deliver_button = fields.Boolean(string="Show Deliver Button", compute='_compute_show_deliver_button', store=False)
    is_collection_point_readonly = fields.Boolean(string="Is Collection Point Readonly", compute='_compute_is_collection_point_readonly', store=False)

    marriage_date = fields.Date('Marriage Date', default=fields.Date.today())
    collection_date = fields.Date('Collection Date', default=fields.Date.today())
    quantity = fields.Float('Quantity', default=1.0)
    amount = fields.Float(
        'Amount',
        related='product_id.list_price',
        store=True,
    )

    advance_donation_amount = fields.Float(
        'Advance Donation Amount',
        store=True,
        default=0.0
    )




    total_amount = fields.Float(
        'Total Amount',
        compute='_compute_total_amount',
        store=True,
        readonly=False
    )


    manual_total = fields.Boolean(default=False)

    def action_set_pending(self, create_return_line=True):
        """
        Create a new welfare record with only the pending disbursement line.
        Copy all available data from the original welfare record to the new one.
        Both the original line and the new line are set to 'pending' state.
        Also creates a return line record.
        """
        action = {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'target': 'current',
        }

        for record in self:
            if record.welfare_id:
                welfare = record.welfare_id

                new_welfare_vals = {
                    'name': welfare.name,
                    'donee_id': welfare.donee_id.id if welfare.donee_id else False,
                    'employee_id': welfare.employee_id.id if welfare.employee_id else False,
                    'is_individual': welfare.is_individual,
                    'date': welfare.date if welfare.date else fields.Date.today(),
                    'state': 'hod_approve',
                    'order_type': welfare.order_type if welfare.order_type else False,
                    'institution_category': welfare.institution_category if welfare.institution_category else False,
                    'subcategory': welfare.subcategory if welfare.subcategory else False,
                    'old_system_id': welfare.old_system_id if welfare.old_system_id else False,
                    'applicantLocationLink': welfare.applicantLocationLink if welfare.applicantLocationLink else False,
                    # Document Fields
                    'application_form': welfare.application_form if welfare.application_form else False,
                    'application_form_name': welfare.application_form_name if welfare.application_form_name else False,
                    'frc': welfare.frc if welfare.frc else False,
                    'frc_name': welfare.frc_name if welfare.frc_name else False,
                    'electricity_bill_file': welfare.electricity_bill_file if welfare.electricity_bill_file else False,
                    'electricity_bill_name': welfare.electricity_bill_name if welfare.electricity_bill_name else False,
                    'gas_bill_file': welfare.gas_bill_file if welfare.gas_bill_file else False,
                    'gas_bill_name': welfare.gas_bill_name if welfare.gas_bill_name else False,
                    'family_cnic': welfare.family_cnic if welfare.family_cnic else False,
                    'family_cnic_name': welfare.family_cnic_name if welfare.family_cnic_name else False,
                    # Remarks Fields
                    'hod_remarks': welfare.hod_remarks if welfare.hod_remarks else False,
                    'member_remarks': welfare.member_remarks if welfare.member_remarks else False,
                    'committee_remarks': welfare.committee_remarks if welfare.committee_remarks else False,
                    'rejection_remarks': welfare.rejection_remarks if welfare.rejection_remarks else False,
                    'portal_review_notes': welfare.portal_review_notes if welfare.portal_review_notes else False,
                    'inquiry_media': welfare.inquiry_media if welfare.inquiry_media else False,
                    # Employee Information
                    'designation': welfare.designation if welfare.designation else False,
                    'company_name': welfare.company_name if welfare.company_name else False,
                    'company_phone': welfare.company_phone if welfare.company_phone else False,
                    'company_address': welfare.company_address if welfare.company_address else False,
                    'service_duration': welfare.service_duration if welfare.service_duration else 0,
                    'monthly_salary': welfare.monthly_salary if welfare.monthly_salary else 0,
                    # House Ownership / Residency Details
                    'residence_type': welfare.residence_type if welfare.residence_type else False,
                    'home_phone_no': welfare.home_phone_no if welfare.home_phone_no else False,
                    'landlord_cnic_no': welfare.landlord_cnic_no if welfare.landlord_cnic_no else False,
                    'landlord_mobile': welfare.landlord_mobile if welfare.landlord_mobile else False,
                    'landlord_name': welfare.landlord_name if welfare.landlord_name else False,
                    'rental_shared_duration': welfare.rental_shared_duration if welfare.rental_shared_duration else 0,
                    'per_month_rent': welfare.per_month_rent if welfare.per_month_rent else 0,
                    'gas_bill': welfare.gas_bill if welfare.gas_bill else 0,
                    'electricity_bill': welfare.electricity_bill if welfare.electricity_bill else 0,
                    'home_other_info': welfare.home_other_info if welfare.home_other_info else False,
                    # Other Finance
                    'monthly_income': welfare.monthly_income if welfare.monthly_income else 0,
                    'outstanding_amount': welfare.outstanding_amount if welfare.outstanding_amount else 0,
                    'monthly_household_expense': welfare.monthly_household_expense if welfare.monthly_household_expense else 0,
                    'bank_account': welfare.bank_account if welfare.bank_account else False,
                    'bank_name': welfare.bank_name if welfare.bank_name else False,
                    'account_no': welfare.account_no if welfare.account_no else False,
                    'institute_name': welfare.institute_name if welfare.institute_name else False,
                    'other_loan': welfare.other_loan if welfare.other_loan else False,
                    # Other Information
                    'aid_from_other_organization': welfare.aid_from_other_organization if welfare.aid_from_other_organization else False,
                    'have_applied_swit': welfare.have_applied_swit if welfare.have_applied_swit else False,
                    'details_1': welfare.details_1 if welfare.details_1 else False,
                    'details_2': welfare.details_2 if welfare.details_2 else False,
                    'driving_license': welfare.driving_license if welfare.driving_license else False,
                    # Request Details
                    'loan_request_amount': welfare.loan_request_amount if welfare.loan_request_amount else 0,
                    'loan_tenure_expected': welfare.loan_tenure_expected if welfare.loan_tenure_expected else False,
                    'security_offered': welfare.security_offered if welfare.security_offered else False,
                    # Family Detail
                    'dependent_person': welfare.dependent_person if welfare.dependent_person else 0,
                    'household_member': welfare.household_member if welfare.household_member else 0,
                    # Inquiry Committee Questions
                    'applicant_occupation': welfare.applicant_occupation if welfare.applicant_occupation else False,
                    'residence_ownership': welfare.residence_ownership if welfare.residence_ownership else False,
                    'total_children': welfare.total_children if welfare.total_children else 0,
                    'boys_count': welfare.boys_count if welfare.boys_count else 0,
                }

                # Create the new welfare record
                new_welfare = self.env['welfare'].create(new_welfare_vals)

                # Copy ONLY this disbursement line to the new welfare with pending state
                record.copy(default={
                    'welfare_id': new_welfare.id,
                    'state': 'pending',
                })

                # Set original line to pending
                record.state = 'return'

                # Create return line only if not already handled by caller
                if create_return_line:
                    record._create_return_line()

                # Return action to open the new welfare record
                action['res_model'] = 'welfare'
                action['res_id'] = new_welfare.id

        return action

    def action_mark_pending(self):
        """Mark the current line as pending."""
        self.write({'state': 'pending'})
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def open_disbursement_popup(self):
        self.ensure_one()
        popup = self.env['welfare.line.disbursement.popup'].create({
            'line_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Disbursement Details',
            'res_model': 'welfare.line.disbursement.popup',
            'res_id': popup.id,
            'view_mode': 'form',
            'view_id': self.env.ref('bn_welfare.view_welfare_line_disbursement_popup_form').id,
            'target': 'new',
            'context': {'form_view_initial_mode': 'view'},
        }

    @api.model
    def create(self, vals):
        in_kind_category = self.env.ref('bn_master_setup.disbursement_category_in_kind', raise_if_not_found=False)
        
        if in_kind_category and vals.get('disbursement_category_id') == in_kind_category.id:
            vals['collection_point'] = 'branch'
        
        return super().create(vals)


    # REMOVED - This write() method was problematic and has been merged with the manual tracking one below
    
    
    @api.model
    def _auto_mark_as_delivered_today(self):
        today = fields.Date.today()
        _logger.info(f"Running scheduled action to auto-mark welfare lines as delivered for today: {today}")
        lines = self.search([('collection_date', '=', today), 
                                    ('state', '=', 'draft'),
                                    ('disbursement_category_id', '=', self.env.ref('bn_master_setup.disbursement_category_in_kind').id),
                                    ('welfare_id.state', '=', 'approve'),
                                    ('collection_point', '=', 'branch'),
                                    ('welfare_id.order_type', 'in', ['one_time'])
                                    ])
        _logger.info(f"Auto-marking {len(lines)} welfare lines as delivered for today")        
        for line in lines:
            if line.welfare_id.order_type == 'one_time' :
                try:
                    _logger.info(f"Auto-marking Welfare  {line.welfare_id.name} as delivered")
                    line.action_delivered()
                except Exception as e:
                    # Optionally log error
                    pass
    
    @api.model
    def _auto_create_bills_for_cash_bank(self):
        """Scheduled action to create bills for Cash + Bank collection on collection date"""
        today = fields.Date.today()
        cash_category = self.env.ref('bn_master_setup.disbursement_category_Cash', raise_if_not_found=False)
        
        if not cash_category:
            return
        
        lines = self.search([
            ('collection_date', '=', today),
            ('state', '=', 'draft'),
            ('disbursement_category_id', '=', cash_category.id),
            ('collection_point', '=', 'bank'),
            ('bill_id', '=', False),
            ('welfare_id.state', '=', 'approve'),
            ('welfare_id.order_type', 'in', ['one_time'])
        ])
        _logger.info(f"Auto-creating bills for {len(lines)} welfare lines")
        for line in lines:
            try:
                line._create_bill()
                line.state = 'delivered'  # Mark as disbursed immediately after bill creation for Cash + Bank
            except Exception as e:
                # Log error but continue processing other lines
                _logger.error(f"Error creating bill for Welfare Line ID {line.id}: {str(e)}")
                pass
    
    def _create_bill(self):
        """Create vendor bill for Cash + Bank collection"""
        if not self.welfare_id.donee_id:
            return
        
        # Get expense account from product or use default
        account = self.product_id.property_account_expense_id or \
                  self.product_id.categ_id.property_account_expense_categ_id
        
        if not account:
            # Get default payable account
            account = self.env['account.account'].search([
                ('account_type', '=', 'expense'),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
        
        # Calculate unit price from total_amount to respect custom amounts
        unit_price = self.total_amount / self.quantity if self.quantity else self.total_amount
        
        invoice_line_vals = {
            'product_id': self.product_id.id,
            'name': self.product_id.name or 'Welfare Payment',
            'quantity': self.quantity,
            'price_unit': unit_price,
            'account_id': account.id if account else False,
            # 'analytic_account_id': self.analytic_account_id.id if self.analytic_account_id else False,
        }
        
        bill_vals = {
            'move_type': 'in_invoice',
            'partner_id': self.welfare_id.donee_id.id,
            'invoice_date': self.collection_date,
            'date': self.collection_date,
            'ref': self.welfare_id.name,
            'invoice_line_ids': [(0, 0, invoice_line_vals)],
            'welfare_line_id': self.id,
        }
        
        bill = self.env['account.move'].create(bill_vals)
        self.bill_id = bill.id
        
        # Auto-post the bill
        bill.action_post()
        
        return bill
                
    @api.depends('disbursement_category_id', 'welfare_id.order_type')
    def _compute_show_deliver_button(self):
        in_kind_category = self.env.ref('bn_master_setup.disbursement_category_in_kind', raise_if_not_found=False)
        cash_category = self.env.ref('bn_master_setup.disbursement_category_Cash', raise_if_not_found=False)
        for rec in self:
            rec.show_deliver_button = False
            if rec.disbursement_category_id:
                if rec.welfare_id.state == 'approve':
                    if in_kind_category and rec.disbursement_category_id.id == in_kind_category.id:
                        # Only show if state is not delivered or disbursed
                        if rec.welfare_id.order_type == "one_time" and rec.state not in ['delivered', 'disbursed']:
                            rec.show_deliver_button = True
                    elif cash_category and rec.disbursement_category_id.id == cash_category.id:
                        rec.show_deliver_button = False
                else:
                    rec.show_deliver_button = False
                
                    
    @api.depends('disbursement_category_id')
    def _compute_fixed_amount_check(self):
        for rec in self:
            rec.fixed_amount_check = rec.disbursement_category_id.name =="In Kind"

    @api.depends('disbursement_category_id')
    def _compute_is_collection_point_readonly(self):
        for rec in self:
            rec.is_collection_point_readonly = rec.disbursement_category_id.name == "In Kind"


    @api.depends('quantity', 'amount', 'advance_donation_amount')
    def _compute_total_amount(self):
        for rec in self:
            if not rec.manual_total:
                amount = rec.quantity * rec.amount
                rec.total_amount = amount - rec.advance_donation_amount if (rec.advance_donation_amount > 0) else amount

    def write(self, vals):
        # Track which orders need checking BEFORE the write
        orders_to_check = self.env['welfare']
        if 'state' in vals and vals['state'] == 'disbursed':
            orders_to_check = self.mapped('welfare_id')
        
        # Track manual amount overrides
        if 'total_amount' in vals:
            vals['manual_total'] = True
        
        # Handle manual_total for multiple records correctly
        # This part is problematic - better to handle in compute or skip
        # The compute method already handles manual_total correctly
        
        # Handle in_kind category auto-selection
        in_kind_category = self.env.ref('bn_master_setup.disbursement_category_in_kind', raise_if_not_found=False)
        if 'disbursement_category_id' in vals:
            if in_kind_category and vals.get('disbursement_category_id') == in_kind_category.id:
                vals['collection_point'] = 'branch'
        
        # Call super to actually save to database
        result = super().write(vals)
        
        # After successful write, check if orders should be disbursed
        if 'state' in vals and vals['state'] == 'disbursed':
            for order in orders_to_check:
                if order and hasattr(order, '_auto_disburse_if_all_lines_delivered'):
                    order._auto_disburse_if_all_lines_delivered()
        
        return result
            
    # @api.depends('total_amount', 'advance_donation_amount')
    # def _compute_net_amount(self):
    #     for rec in self:
    #         if rec.manual_net_total:
    #             rec.net_amount = rec.total_amount - rec.advance_donation_amount
    #         else:
    #             rec.net_amount = rec.total_amount
        
    @api.depends('disbursement_application_type_id.product_category_id')
    def _compute_product_domain(self):
        for rec in self:
            product_category = rec.disbursement_application_type_id.product_category_id
            if not product_category:
                rec.product_domain = [(5, 0, 0)]
                continue

            products = self.env['product.product'].search([
                ('categ_id', 'child_of', product_category.id),
                ('is_welfare', '=', True),
            ])
            rec.product_domain = [(6, 0, products.ids)]
    @api.depends('disbursement_application_type_id')
    def _compute_analytic_account_domain(self):
        for rec in self:
            rec.analytic_account_domain = ""
            if rec.disbursement_application_type_id and rec.disbursement_application_type_id.analytic_account_ids:
                analytic_account_ids = rec.disbursement_application_type_id.analytic_account_ids.ids
                rec.analytic_account_domain = str([('id', 'in', analytic_account_ids)])
    
    # @api.depends('disbursement_application_type_id')
    # def _compute_warehouse_domain(self):
    #     for rec in self:
    #         rec.warehouse_domain = ""
    #         if rec.disbursement_application_type_id and rec.disbursement_application_type_id.analytic_account_ids:
    #             warehouse_ids = rec.disbursement_application_type_id.analytic_account_ids.ids
    #             rec.warehouse_domain = str([('id', 'in', warehouse_ids)])
    
    @api.onchange('disbursement_category_id')
    def _onchange_disbursement_category_id(self):
        """Auto-select branch for In Kind category"""
        in_kind_category = self.env.ref('bn_master_setup.disbursement_category_in_kind', raise_if_not_found=False)
        if in_kind_category and self.disbursement_category_id.id == in_kind_category.id:
            self.collection_point = 'branch'
    def can_disburse(self):
        """Check if line can be disbursed (not already collected/returned/disbursed)"""
        return self.state not in ['collected', 'return', 'disbursed']

    def can_return(self):
        """Check if line can be returned"""
        return self.payment_type == 'assigned_officer' and self.state == 'pending'            
       
    def action_disbursed(self):
        """
        Mark as disbursed or collected based on payment type
        PREVENT re-processing already collected or returned lines
        """
        for line in self:
            if line.state not in ['draft', 'delivered']:
                raise ValidationError(_(
                    "This welfare line cannot be paid again. "
                    "Current state is '%s'. Only Draft or Delivery Created lines can be paid."
                ) % line.state)
        
            # Mark as disbursed or collected based on payment type
            line.state = 'collected' if line.payment_type == 'assigned_officer' else 'disbursed'
            
            if getattr(line, 'advance_donation_line_id', False):
                line.advance_donation_line_id.write({'disbursed_amount': line.advance_donation_amount})
            
            if line.welfare_id:
                line.welfare_id._auto_disburse_if_all_lines_delivered()
        
        return True
                            
    def action_delivered(self):
            _logger.info(f"Delivery Method Triggered {self.welfare_id.name} with product {self.product_id.name} and quantity {self.quantity}")
            in_kind_category = self.env.ref('bn_master_setup.disbursement_category_in_kind')
            if self.disbursement_category_id == in_kind_category:        
                StockPicking = self.env['stock.picking']
                StockMove = self.env['stock.move']
                StockMoveLine = self.env['stock.move.line']
                
                # Use warehouse from welfare line, fallback to default
                # if self.warehouse_id:
                #     warehouse = self.warehouse_id
                #     picking_type = warehouse.out_type_id
                #     location_src = warehouse.lot_stock_id
                # else:
                picking_type = self.env.ref('stock.picking_type_out')
                location_src = self.env['stock.location'].search([('usage', '=', 'internal')], limit=1)
                
                location_dest = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)
                
                picking_vals = {
                    'partner_id': self.welfare_id.donee_id.id,
                    'picking_type_id': picking_type.id,
                    'location_id': location_src.id if location_src else False,
                    'location_dest_id': location_dest.id if location_dest else False,
                    'origin': self.welfare_id.name,
                    'welfare_line_id': self.id,

                }
                picking = StockPicking.create(picking_vals)
                _logger.info(f"Created stock picking  for welfare record {picking.name} with product {self.product_id.name} and quantity {self.quantity}")
                move_vals = {
                    'name': self.product_id.display_name,
                    'product_id': self.product_id.id,
                    'product_uom_qty': self.quantity,
                    'product_uom': self.product_id.uom_id.id,
                    'picking_id': picking.id,
                    'location_id': location_src.id if location_src else False,
                    'location_dest_id': location_dest.id if location_dest else False,
                }
                move = StockMove.create(move_vals)
                move_line_vals = {
                    'move_id': move.id,
                    'product_id': self.product_id.id,
                    'product_uom_id': self.product_id.uom_id.id,
                    'quantity': self.quantity,
                    'picking_id': picking.id,
                    'location_id': location_src.id if location_src else False,
                    'location_dest_id': location_dest.id if location_dest else False,
                }
                StockMoveLine.create(move_line_vals)
                picking.action_assign()
                self.state = 'delivered'


    def mark_selected_as_collected(self):
        """Mark all selected disbursement lines as collected"""
        for line in self.disbursement_line_ids:
            if line.state != 'collected':
                line.write({'state': 'collected'})
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }        
    

    def action_return_to_pos(self, **kwargs):
        """
        Return collected amount to POS for Assigned Officer (Marfat) payments
        Money comes BACK to the company (Donee returns it)
        """
        self.ensure_one()
        
        # Validation checks
        if self.payment_type != 'assigned_officer':
            raise ValidationError(_(
                "Return is only allowed for 'Assigned Officer (Marfat)' payment type. "
                "Current payment type: %s" % self.payment_type
            ))
        
        if self.state != 'pending':
            raise ValidationError(_(
                "Return is only allowed for lines in 'Pending' state. "
                "Current state: %s. Only 'Pending' lines can be returned."
            ) % self.state)
        
        if not self.welfare_id.donee_id:
            raise ValidationError(_("No donee associated with this welfare line."))
        
        try:
            # Create journal entry for money coming IN to company
            return_receipt = self._create_return_receipt()
            
            # Reset the line so the welfare can be approved and paid again.
            self.write({
                'state': 'return',
                'return_date': fields.Datetime.now(),
                'return_bill_id': return_receipt.id,
                'returned_by': self.env.user.id,
            })

            self.welfare_id.write({'state': 'return'})
            
            # Post message
            self.welfare_id.message_post(body=f"""
                <b>💰 Welfare Line Returned (Money Received Back)</b><br/>
                <b>Product:</b> {self.product_id.name}<br/>
                <b>Amount Returned:</b> {self.total_amount} {self.currency_id.symbol}<br/>
                <b>Return Date:</b> {fields.Datetime.now()}<br/>
                <b>Payment Type:</b> Assigned Officer (Marfat)<br/>
                <b>Returned By:</b> {self.env.user.name}<br/>
                <b>Status:</b> Money returned from Donee → Company cash increased
            """)
            
            return True
            
        except Exception as e:
            _logger.error(f"Error returning welfare line {self.id}: {str(e)}")
            raise ValidationError(_("Failed to process return: %s" % str(e)))

    def _create_return_receipt(self):
        """
        Create a journal entry for money returned from Donee
        This INCREASES company cash (money coming IN)
        """
        # Find cash or bank account
        cash_account = self.env['account.account'].search([
            ('account_type', 'in', ['asset_cash', 'asset_bank']),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        if not cash_account:
            raise ValidationError(_("No cash/bank account found to process return."))
        
        # Find expense/income account for the product
        expense_account = self.product_id.property_account_expense_id or \
                        self.product_id.categ_id.property_account_expense_categ_id
        
        if not expense_account:
            # Fallback to a default expense account
            expense_account = self.env['account.account'].search([
                ('account_type', '=', 'expense'),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
        
        # Create journal entry (money IN)
        journal = self.env['account.journal'].search([
            ('type', 'in', ['cash', 'bank', 'general']),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        move_vals = {
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f"WELFARE-RETURN-{self.welfare_id.name}",
            'line_ids': [
                (0, 0, {
                    'name': f'Return from {self.welfare_id.donee_id.name}',
                    'account_id': cash_account.id,
                    'debit': self.total_amount,  # Money IN - Cash increases
                    'credit': 0,
                    'partner_id': self.welfare_id.donee_id.id,
                }),
                (0, 0, {
                    'name': f'Welfare Return - {self.product_id.name}',
                    'account_id': expense_account.id,
                    'debit': 0,
                    'credit': self.total_amount,  # Reduce expense/record return
                    'partner_id': self.welfare_id.donee_id.id,
                }),
            ]
        }
        
        move = self.env['account.move'].create(move_vals)
        move.action_post()
        
        _logger.info(f"Created return journal entry {move.name} for amount {self.total_amount}")
        
        return move

    def _create_pos_return_order(self):
        """
        Create a POS return order if POS integration exists
        This records the return in POS system
        """
        # Check if POS module is installed
        if 'pos.order' not in self.env:
            return None
        
        # Look for original POS order for this donee around the collection date
        original_pos_order = self.env['pos.order'].search([
            ('partner_id', '=', self.welfare_id.donee_id.id),
            ('state', '=', 'paid'),
            ('date_order', '>=', self.collection_date),
        ], limit=1)
        
        if not original_pos_order:
            _logger.warning(f"No original POS order found for donee {self.welfare_id.donee_id.name}")
            return None
        
        # Create return order with POSITIVE amount (money coming IN)
        return_order_vals = {
            'partner_id': self.welfare_id.donee_id.id,
            'amount_total': self.total_amount,  # ✅ POSITIVE (not negative)
            'amount_paid': self.total_amount,   # ✅ POSITIVE
            'amount_return': 0,                 # ✅ No return amount needed
            'state': 'paid',
            'is_return': True,
            'original_order_id': original_pos_order.id,
            'lines': [(0, 0, {
                'product_id': self.product_id.id,
                'qty': self.quantity,           # ✅ POSITIVE (not negative)
                'price_unit': self.total_amount / self.quantity if self.quantity else self.total_amount,
                'price_subtotal': self.total_amount,      # ✅ POSITIVE
                'price_subtotal_incl': self.total_amount, # ✅ POSITIVE
            })],
        }
        
        pos_return = self.env['pos.order'].create(return_order_vals)
        
        _logger.info(f"Created POS return order {pos_return.name} for amount {self.total_amount}")
        
        return pos_return
    def action_return_to_draft(self):
        """Allow returning a line to draft state and record state to hod approve for re-processing"""
        for line in self:
            if line.state != 'return':
                raise ValidationError(_(
                    "Only lines in 'Return' state can be moved back to Draft. "
                    "Current state: %s. Only 'Return' lines can be reset." % line.state
                ))
        
        self.write({'state': 'draft'})
        self.welfare_id.write({'state': 'hod_approve'})
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }