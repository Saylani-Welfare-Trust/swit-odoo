from odoo import models, fields,_,api
from odoo.exceptions import UserError, ValidationError
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
    ('cancel', 'Cancelled'),
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
    _inherit = ['pos.link.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Welfare Line"

    return_date = fields.Datetime('Return Date', readonly=True)
    return_bill_id = fields.Many2one('account.move', string='Return Bill', readonly=True)
    returned_by = fields.Many2one('res.users', string='Returned By', default=lambda self: self.env.user)
    #welfare related field name order_type put in welfare line
    order_type = fields.Selection(
        related='welfare_id.order_type',
        string='Order Type',
        store=True,
        readonly=True,
    )    
    product_domain = fields.Char('Product Domain', compute='_compute_product_domain', default="[]", store=True)
    analytic_account_domain = fields.Char('Analytic Account Domain', compute='_compute_analytic_account_domain', default="[]", store=True)
    employee_category_id_officer = fields.Many2one(
        'hr.employee.category', 
        string='Officer Employee Category', 
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
    is_hod = fields.Boolean('Is HOD', readonly=True, help="Line added automatically at HOD Approval.")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Branch", index='btree_not_null')
    disbursement_category_id = fields.Many2one('disbursement.category', string="Disbursement Category")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    disbursement_application_type_id = fields.Many2one('disbursement.application.type', string="Disbursement Application Type")
    bill_id = fields.Many2one('account.move', string="Bill", readonly=True)
    

    on_hand_qty = fields.Float(
        string='On Hand Quantity',
        compute='_compute_on_hand_qty'
    )

    @api.depends('product_id')
    def _compute_on_hand_qty(self):
        for rec in self:
            rec.on_hand_qty = rec.product_id.qty_available if rec.product_id else 0.0
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    fixed_amount_check = fields.Boolean('Fixed Amount Check', default=False, compute='_compute_fixed_amount_check')
    is_cash_category = fields.Boolean('Is Cash Category', compute='_compute_is_cash_category')
    show_deliver_button = fields.Boolean(string="Show Deliver Button", compute='_compute_show_deliver_button', store=False)
    is_collection_point_readonly = fields.Boolean(string="Is Collection Point Readonly", compute='_compute_is_collection_point_readonly', store=False)

    marriage_date = fields.Date('Marriage Date', default=fields.Date.context_today)
    collection_date = fields.Date('Collection Date', default=fields.Date.context_today)
    quantity = fields.Float('Quantity', default=1.0)
    amount = fields.Float(
        'Amount',
        related='product_id.list_price',
        store=True,
    )

    advance_donation_amount = fields.Float(
        'Donor Acc',
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
    media_ids = fields.Many2many(
        'ir.attachment',
        'welfare_line_media_rel',
        'line_id',
        'attachment_id',
        string='Media (Images/Videos)',
    )
    media_count = fields.Integer(compute='_compute_media_count', string='Media Count')

    @api.depends('media_ids')
    def _compute_media_count(self):
        for rec in self:
            rec.media_count = len(rec.media_ids)

    def action_mark_pending(self):
        """Mark the current line as pending."""
        if any(line.state not in ('collected', 'pending') for line in self):
            raise UserError(_("Only lines collected by the officer can be marked as Pending."))
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
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # By name: older databases have two "In Kind" categories (master setup and welfare data)
            if self.env['disbursement.category'].browse(vals.get('disbursement_category_id')).name == 'In Kind':
                vals['collection_point'] = 'branch'
        return super().create(vals_list)


    # REMOVED - This write() method was problematic and has been merged with the manual tracking one below
    
    
    @api.model
    def _auto_mark_as_delivered_today(self):
        today = fields.Date.today()
        _logger.info(f"Running scheduled action to auto-mark welfare lines as delivered for today: {today}")
        # <= today: lines approved after their collection date are still delivered
        lines = self.search([('collection_date', '<=', today),
                                    ('state', '=', 'draft'),
                                    ('disbursement_category_id.name', '=', 'In Kind'),
                                    ('welfare_id.state', '=', 'approve'),
                                    # empty: In Kind lines whose branch was never filled in (read-only for In Kind)
                                    ('collection_point', 'in', ['branch', False]),
                                    ('welfare_id.order_type', 'in', ['one_time'])
                                    ])
        _logger.info(f"Auto-marking {len(lines)} welfare lines as delivered for today")
        for line in lines:
            if line.welfare_id.order_type == 'one_time' :
                try:
                    _logger.info(f"Auto-marking Welfare  {line.welfare_id.name} as delivered")
                    with self.env.cr.savepoint():
                        line.action_delivered()
                except Exception:
                    _logger.exception("Could not create delivery for welfare %s line %s", line.welfare_id.name, line.id)
    
    @api.model
    def _auto_create_bills_for_cash_bank(self):
        """Scheduled action to create bills for Cash + Bank collection on collection date"""
        today = fields.Date.today()
        cash_category = self.env.ref('bn_welfare.disbursement_category_Cash', raise_if_not_found=False)
        
        if not cash_category:
            return
        
        lines = self.search([
            ('collection_date', '<=', today),
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
                # a failing line is rolled back alone; the others still get their bill
                with self.env.cr.savepoint():
                    line._create_bill()
                    # delivered once its bill exists (no donee: no bill, left as is)
                    if line.bill_id:
                        line.state = 'delivered'
            except Exception:
                _logger.exception("Could not create the bill of welfare line %s", line.id)
    
    def _create_bill(self):
        """Create vendor bill for Cash + Bank collection"""
        if not self.welfare_id.donee_id:
            return
        
        # Get expense account from product or use default
        account = self.product_id.property_account_expense_id or \
                  self.product_id.categ_id.property_account_expense_categ_id
        
        if not account:
            # never the first expense account found: the product says where it goes
            raise UserError(_('Set an expense account on %s or its category.') % self.product_id.display_name)
        
        # Calculate unit price from total_amount to respect custom amounts
        unit_price = self.total_amount / self.quantity if self.quantity else self.total_amount
        
        invoice_line_vals = {
            'product_id': self.product_id.id,
            'name': self.product_id.name or 'Welfare Payment',
            'quantity': self.quantity,
            'price_unit': unit_price,
            'account_id': account.id if account else False,
            'analytic_distribution': {str(self.analytic_account_id.id): 100} if self.analytic_account_id else False,
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
        
        bill = self.env['account.move'].with_context(default_source_record_ref='%s,%s' % (self[:1]._name, self[:1].id)).create(bill_vals)
        self.bill_id = bill.id
        
        # Auto-post the bill
        bill.action_post()
        
        return bill
                
    @api.depends('disbursement_category_id', 'welfare_id.order_type')
    def _compute_show_deliver_button(self):
        in_kind_category = self.env.ref('bn_welfare.disbursement_category_in_kind', raise_if_not_found=False)
        cash_category = self.env.ref('bn_welfare.disbursement_category_Cash', raise_if_not_found=False)
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
    def _compute_is_cash_category(self):
        for rec in self:
            rec.is_cash_category = rec.disbursement_category_id.name == "Cash"

    @api.depends('disbursement_category_id')
    def _compute_is_collection_point_readonly(self):
        for rec in self:
            rec.is_collection_point_readonly = rec.disbursement_category_id.name == "In Kind"


    @api.depends('quantity', 'amount', 'advance_donation_amount', 'disbursement_category_id')
    def _compute_total_amount(self):
        for rec in self:
            # In Kind total is read-only, so it always follows quantity x price
            if not rec.manual_total or rec.fixed_amount_check:
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
        if 'disbursement_category_id' in vals:
            if self.env['disbursement.category'].browse(vals['disbursement_category_id']).name == 'In Kind':
                vals['collection_point'] = 'branch'
        
        # Call super to actually save to database
        result = super().write(vals)
        
        # After successful write, check if orders should be disbursed
        if 'state' in vals and vals['state'] == 'disbursed':
            for order in orders_to_check:
                if order and hasattr(order, '_auto_disburse_if_all_lines_delivered'):
                    order._auto_disburse_if_all_lines_delivered()
        
        return result
            
    @api.model
    def _refresh_product_domain(self):
        """Upgrade: lines saved with the old "all products" domain get the Is Welfare one."""
        lines = self.search([('product_domain', 'in', ('[]', False))])
        if lines:
            self.env.add_to_compute(self._fields['product_domain'], lines)
            lines.flush_recordset(['product_domain'])

    @api.constrains('product_id', 'is_hod', 'disbursement_application_type_id')
    def _check_welfare_product(self):
        """What the product picker offers, also on save (import / RPC). HOD lines are
        added at HOD Approval from the HOD products."""
        for line in self.filtered(lambda l: l.product_id and not l.is_hod):
            if not line.product_id.is_welfare:
                raise ValidationError(_("%s is not a Welfare product: tick 'Is Welfare' on the product first.")
                                      % line.product_id.display_name)
            category = line.disbursement_application_type_id.product_category_id
            if category and not self.env['product.product'].sudo().search_count(
                    [('id', '=', line.product_id.id), ('categ_id', 'child_of', category.id)]):
                raise ValidationError(_("%(product)s is not in the category %(category)s of the application type.") % {
                    'product': line.product_id.display_name, 'category': category.display_name})

    @api.depends('disbursement_application_type_id.product_category_id')
    def _compute_product_domain(self):
        for rec in self:
            # Is Welfare products, of the application type's category when it has one
            domain = [('product_tmpl_id.is_welfare', '=', True)]
            product_category = rec.disbursement_application_type_id.product_category_id
            if product_category:
                domain.append(('categ_id', 'child_of', product_category.id))
            rec.product_domain = str(domain)
    @api.depends('disbursement_application_type_id')
    def _compute_analytic_account_domain(self):
        for rec in self:
            rec.analytic_account_domain = "[]"
            if rec.disbursement_application_type_id and rec.disbursement_application_type_id.analytic_account_ids:
                analytic_account_ids = rec.disbursement_application_type_id.analytic_account_ids.ids
                rec.analytic_account_domain = str([('id', 'in', analytic_account_ids)])
    
    
    @api.onchange('disbursement_application_type_id')
    def _onchange_disbursement_application_type_id(self):
        """Take the category set on the application type in master setup"""
        if self.disbursement_application_type_id.disbursement_category_id:
            self.disbursement_category_id = self.disbursement_application_type_id.disbursement_category_id

    @api.onchange('disbursement_category_id')
    def _onchange_disbursement_category_id(self):
        """Auto-select branch for In Kind category"""
        # By name: older databases have two "In Kind" categories (master setup and welfare data)
        if self.disbursement_category_id.name == 'In Kind':
            self.collection_point = 'branch'
        # Quantity is read-only for Cash, so don't leave a quantity from another category
        if self.disbursement_category_id.name == "Cash":
            self.quantity = 1

    def _check_welfare_payable(self):
        """Lines are paid once their welfare is approved (HOD lines from HOD
        approval on, the HOD decides on them)."""
        self.ensure_one()
        allowed = ('approve', 'recurring')
        if self.is_hod:
            allowed += ('hod_approve', 'mem_approve')
        if self.welfare_id.state not in allowed:
            raise ValidationError(_('%(welfare)s is not approved yet (status: %(state)s): its lines cannot be paid.') % {
                'welfare': self.welfare_id.name,
                'state': dict(self.welfare_id._fields['state'].selection).get(self.welfare_id.state)})

    @api.model
    def pos_check_payable(self, ids):
        """POS: called before the payment is validated, so a line that
        cannot be paid stops the order instead of the cash going out."""
        for line in self.browse(ids):
            if line.state not in ('draft', 'delivered'):
                raise ValidationError(_("Welfare line %s is already %s.") % (
                    line.display_name, dict(self._fields['state'].selection).get(line.state)))
            line._check_welfare_payable()
        return True

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
            line._check_welfare_payable()

            line.state = 'collected' if line.payment_type == 'assigned_officer' else 'disbursed'

            if line.welfare_id:
                line.welfare_id._auto_disburse_if_all_lines_delivered()

        return True

    def action_cancel_from_pos(self):
        """Cancel the HOD lines the cashier removed from the POS order (welfare lines are never deleted)."""
        lines = self.exists().filtered(lambda l: l.is_hod and l.state == 'draft')
        for welfare in lines.welfare_id:
            products = lines.filtered(lambda l: l.welfare_id == welfare).product_id
            welfare._message_log(body=_("HOD line(s) removed at POS by %s: %s") % (
                self.env.user.name, ", ".join(products.mapped('display_name'))
            ))
        lines.write({'state': 'cancel'})
        return True

    def _get_delivery_locations(self):
        """The Welfare Delivery operation type of the user's warehouse, with
        its source and customer locations."""
        picking_type = self.env['stock.warehouse']._get_program_type('welfare')
        location_src = picking_type.default_location_src_id or picking_type.warehouse_id.lot_stock_id
        location_dest = picking_type.default_location_dest_id or self.env.ref('stock.stock_location_customers')
        return picking_type, location_src, location_dest

    def action_delivered(self):
        for line in self:
            line._action_delivered_one()

    def _action_delivered_one(self):
            _logger.info(f"Delivery Method Triggered {self.welfare_id.name} with product {self.product_id.name} and quantity {self.quantity}")
            if self.state != 'draft':
                raise ValidationError(_('A delivery is only created for a Draft line (%s).') % self.display_name)
            # By name: older databases have two "In Kind" categories (master setup and welfare data)
            if self.disbursement_category_id.name == 'In Kind':
                StockPicking = self.env['stock.picking']
                StockMove = self.env['stock.move']
                StockMoveLine = self.env['stock.move.line']
                
                picking_type, location_src, location_dest = self._get_delivery_locations()

                picking_vals = {
                    'partner_id': self.welfare_id.donee_id.id,
                    'picking_type_id': picking_type.id,
                    'location_id': location_src.id if location_src else False,
                    'location_dest_id': location_dest.id if location_dest else False,
                    'origin': self.welfare_id.name,
                    'source_record_ref': '%s,%s' % (self.welfare_id._name, self.welfare_id.id),
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
            self.welfare_id._message_log(body=f"""
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
        # the configured Welfare Return Journal and its own account
        journal = (self.company_id or self.env.company)._get_welfare_return_journal()
        cash_account = journal.default_account_id
        if not cash_account:
            raise ValidationError(_("The Welfare Return Journal %s has no default account.") % journal.display_name)
        
        # Find expense/income account for the product
        expense_account = self.product_id.property_account_expense_id or \
                        self.product_id.categ_id.property_account_expense_categ_id
        
        if not expense_account:
            raise UserError(_('Set an expense account on %s or its category.') % self.product_id.display_name)
        
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
                    'analytic_distribution': {str(self.analytic_account_id.id): 100} if self.analytic_account_id else False,
                    'credit': 0,
                    'partner_id': self.welfare_id.donee_id.id,
                }),
                (0, 0, {
                    'name': f'Welfare Return - {self.product_id.name}',
                    'account_id': expense_account.id,
                    'debit': 0,
                    'credit': self.total_amount,  # Reduce expense/record return
                    'analytic_distribution': {str(self.analytic_account_id.id): 100} if self.analytic_account_id else False,
                    'partner_id': self.welfare_id.donee_id.id,
                }),
            ]
        }
        
        move = self.env['account.move'].with_context(default_source_record_ref='%s,%s' % (self[:1]._name, self[:1].id)).create(move_vals)
        move.action_post()
        
        _logger.info(f"Created return journal entry {move.name} for amount {self.total_amount}")
        
        return move

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