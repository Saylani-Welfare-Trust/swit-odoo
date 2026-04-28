from odoo import models, fields, api
from odoo.fields import Date
from odoo.exceptions import UserError

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


state_selection = [
    ('draft', 'Draft'),
    ('delivered', 'Delivery Created'),
    ('disbursed', 'Disbursed'),
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


    product_domain = fields.Char('Product Domain', compute='_compute_product_domain', default="[]", store=True)
    analytic_account_domain = fields.Char('Analytic Account Domain', compute='_compute_analytic_account_domain', default="[]", store=True)

    # order_type field moved to main welfare model
    collection_point = fields.Selection(selection=collection_point_selection, string="Collection Point", store=True )
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


    # @api.depends('quantity', 'amount', 'advance_donation_amount')
    # def _compute_total_amount(self):
    #     for rec in self:
    #         if not rec.manual_total:
    #             amount = rec.quantity * rec.amount
    #             rec.total_amount = amount - rec.advance_donation_amount if (rec.advance_donation_amount > 0) else amount
    #             _logger.info(f"Computed total_amount for {rec.total_amount}")
    @api.depends('quantity', 'amount', 'advance_donation_amount', 'manual_total')
    def _compute_total_amount(self):
        for rec in self:
            if not rec.manual_total:
                amount = rec.quantity * rec.amount
                rec.total_amount = amount - rec.advance_donation_amount if (rec.advance_donation_amount > 0) else amount
                _logger.info(f"Auto-computed total_amount: {rec.total_amount}")
            else:
                _logger.info(f"Skipping compute for {rec.id} because manual_total=True, keeping total_amount: {rec.total_amount}")

    import logging

    _logger = logging.getLogger(__name__)
    def write(self, vals):
        _logger.info(f"=== WRITE CALLED ===")
        _logger.info(f"Input vals: {vals}")
        
        # Handle in_kind category auto-selection
        in_kind_category = self.env.ref('bn_master_setup.disbursement_category_in_kind', raise_if_not_found=False)
        if 'disbursement_category_id' in vals:
            if in_kind_category and vals.get('disbursement_category_id') == in_kind_category.id:
                vals['collection_point'] = 'branch'
        
        # If manually setting total_amount
        if 'total_amount' in vals:
            _logger.info(f"Manual total_amount detected: {vals['total_amount']}")
            vals['manual_total'] = True
            
            ad_amount = self.advance_donation_amount
            vals['total_amount'] = vals['total_amount'] - ad_amount
            _logger.info(f"After advance subtraction: {vals['total_amount']}")
        
        # # If only updating advance_donation_amount on a manual_total record
        elif 'advance_donation_amount' in vals:
            _logger.info(f"Updating advance on manual_total record")
            old_advance = self.advance_donation_amount
            new_advance = vals['advance_donation_amount']
            # Adjust total_amount by the change in advance
            if 'total_amount' not in vals:
                vals['total_amount'] = self.total_amount - (new_advance - old_advance)
                _logger.info(f"Adjusted total_amount from {self.total_amount} to {vals['total_amount']}")
        
        _logger.info(f"Final vals before super write: {vals}")
        result = super().write(vals)
        _logger.info(f"After write - total_amount: {self.total_amount}, manual_total: {self.manual_total}")
        
        return result
    # def write(self, vals):
    #     # Track manual amount overrides
    #     if 'total_amount' in vals:
    #         vals['manual_total'] = True
        
    #     # Preserve manually set total_amount when not in vals but flag is True
    #     if self.manual_total and 'total_amount' not in vals:
    #         vals['total_amount'] = self.total_amount - self.advance_donation_amount if (self.advance_donation_amount > 0) else self.total_amount
    
        
    #     # Handle in_kind category auto-selection
    #     in_kind_category = self.env.ref('bn_master_setup.disbursement_category_in_kind', raise_if_not_found=False)
    #     if 'disbursement_category_id' in vals:
    #         if in_kind_category and vals.get('disbursement_category_id') == in_kind_category.id:
    #             vals['collection_point'] = 'branch'
        
    #     return super().write(vals)
            
    # @api.depends('total_amount', 'advance_donation_amount')
    # def _compute_net_amount(self):
    #     for rec in self:
    #         if rec.manual_net_total:
    #             rec.net_amount = rec.total_amount - rec.advance_donation_amount
    #         else:
    #             rec.net_amount = rec.total_amount
        
    @api.depends('disbursement_application_type_id')
    def _compute_product_domain(self):
        for rec in self:
            rec.product_domain = ""

            category_id = rec.disbursement_application_type_id.product_category_id.id
            
            if category_id:
                rec.product_domain = str([('categ_id', '=', category_id), ('is_welfare', '=', True)])
    
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
       
    def action_disbursed(self):
        """Mark welfare line as disbursed"""
        _logger.info(f"Marking welfare line {self.id} as disbursed")
        self.state = 'disbursed'
        _logger.info(f"Updating advance donation line {self.advance_donation_line_id.id} with disbursed amount {self.advance_donation_amount}")

        if self.advance_donation_line_id:
            if self.advance_donation_amount > 0:
                self.advance_donation_line_id.write({'disbursed_amount':self.advance_donation_line_id.disbursed_amount + self.advance_donation_amount})

            if self.advance_donation_id.contract_type == 'open_contract':
                _logger.info(f"Creating disbursement line for open contract with advance amount {self.advance_donation_amount}")
                total_amount = self.total_amount or 0.0
                advance_amount = self.advance_donation_amount
                final_amount = advance_amount

                # Only create disbursement line if amounts are valid (non-negative)
                if final_amount >= 0 and advance_amount >= 0:
                    disbursement_line = self.env['advance.donation.disbursement.line'].create({
                        'advance_donation_id': self.advance_donation_id.id,
                        'advance_donation_line_id': self.advance_donation_line_id.id,
                        'product_id': self.product_id.id,
                        'date': fields.Date.today(),
                        'total_amount': total_amount,
                        'advance_amount': advance_amount,
                        'disbursed_amount': final_amount,
                        'disbursed_record': self.welfare_id.name,

                        'welfare_id': self.welfare_id.id,
                        # 'recurring_line_id': self.recurring_line_id.id,
                        # 'microfinance_id': self.microfinance_id.id,
                    })
                    # raise UserError(f"Disbursement line created for open contract with advance amount {disbursement_line}")
                else:
                    _logger.warning(f"Skipped creating disbursement line for welfare {self.welfare_id.name}: "
                                  f"final_amount={final_amount}, advance_amount={advance_amount}")
        
        # Update welfare parent if all lines are now delivered/disbursed
        if self.welfare_id:
            _logger.info(f"Calling _auto_disburse_if_all_lines_delivered for welfare {self.welfare_id.name}")
            self.welfare_id._auto_disburse_if_all_lines_delivered()
    
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