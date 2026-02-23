from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date, timedelta

class AdvanceDonation(models.Model):
    _name = 'advance.donation'
    

    name = fields.Char(string="Name", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    donor_id = fields.Many2one(
        'res.partner', 
        string='Donor',
        domain=[('category_id.name', '=', 'Donor')]
    )
    category_id = fields.Many2one('advance.donation.category', string='Category')
    contract_type = fields.Selection([('product', 'Quantity Based'),
                                     ('frequency', 'Frequency Based')],
                                    string='Contract Type', default='product')

    payment_type = fields.Selection([('cash', 'Cash'),
                                    ('credit', 'Credit')],
                                   string='Payment Type', default='cash')

    total_no_of_product = fields.Integer('Total No of Products')
    donation_slip_ids = fields.Many2many('advance.donation.receipt', 'rel_2', string='Donation Slip')

    contract_frequency = fields.Selection([('daily', 'Daily'),
                                    ('weekly', 'Weekly')],
                                   string='Frequency', default='daily')


    product_id = fields.Many2one('product.product', 'Product')
    product_domain_ids = fields.Many2many('product.product')
    amount_percentage = fields.Float('Percentage')

    no_of_product = fields.Integer('No of Product')
    contract_start_date = fields.Date(string='Start Date')
    contract_end_date = fields.Date(string='End Date')
    no_of_days = fields.Integer('No of Days')
    no_of_weeks = fields.Integer('No of Weeks')

    is_revert = fields.Boolean()
    approval_1_remarks = fields.Html(string="Remarks")
    approval_2_remarks = fields.Html(string="Remarks")

    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)
    total_product_amount = fields.Monetary('Total Amount', currency_field='currency_id')
    paid_amount = fields.Monetary('Paid Amount', compute='_compute_amount')
    remaining_amount = fields.Monetary('Remaining Amount', compute='_compute_amount')
    
    # New fields for balance management
    total_balance = fields.Monetary('Total Balance', currency_field='currency_id', compute='_compute_total_balance', store=False)
    # manual_payment_amount = fields.Monetary('Manual Payment Amount', currency_field='currency_id', default=0 ,store=True)
    # available_balance = fields.Monetary('Available Balance', currency_field='currency_id', compute='_compute_available_balance', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approval_1', 'Approval 1'),
        ('approval_2', 'Approval 2'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')],
        default='draft',
        string='Status')

    advance_donation_lines = fields.One2many('advance.donation.line', 'advance_donation_id')
    donation_slip_usage_lines = fields.One2many('advance.donation.slip.usage', 'advance_donation_id')

    approved_date = fields.Datetime('Approved Date')
    is_fully_paid = fields.Boolean(compute='_compute_fully_paid')
    is_fully_disbursed = fields.Boolean(compute='_compute_fully_disbursed', store=True)


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('advance.donation') or ('New')
        return super().create(vals)

    @api.depends('advance_donation_lines')
    def _compute_amount(self):
        for rec in self:
            paid_amount = 0
            remaining_amount = 0

            for record in rec.advance_donation_lines:
                paid_amount += record.paid_amount
                remaining_amount += record.remaining_amount

            rec.paid_amount = paid_amount
            rec.remaining_amount = remaining_amount

    @api.depends('advance_donation_lines.is_disbursed')
    def _compute_fully_disbursed(self):
        donation_length = len(self.advance_donation_lines)
        disbursed_records = self.advance_donation_lines.filtered(
            lambda line: line.is_disbursed == True
        )
        disbursed_records = len(disbursed_records)
        if donation_length <= disbursed_records:
            self.is_fully_disbursed = True
        else:
            self.is_fully_disbursed = False
    
    @api.depends('donor_id', 'donation_slip_usage_lines', 'donation_slip_usage_lines.usage_amount')
    def _compute_total_balance(self):
        """Calculate total balance from all paid donation receipts for this donor
        Note: Disbursement does not affect balance - only payment allocation does"""
        for rec in self:
            if rec.donor_id:
                # Get all paid donation receipts for this donor
                donation_receipts = self.env['advance.donation.receipt'].search([
                    ('donor_id', '=', rec.donor_id.id),
                    ('state', '=', 'paid'),
                ])
                
                # Force recompute of each receipt's amounts to get fresh values
                for receipt in donation_receipts:
                    receipt._compute_amount()
                
                # Sum remaining amounts (receipt.amount - receipt.used_amount)
                rec.total_balance = sum(donation_receipts.mapped('remaining_amount'))
            else:
                rec.total_balance = 0
    
    # @api.depends('total_balance', 'manual_payment_amount')
    # def _compute_available_balance(self):
    #     """Calculate available balance after manual payment"""
    #     for rec in self:
    #         rec.available_balance = rec.total_balance - rec.manual_payment_amount

    def compute_donation(self):
        self.advance_donation_lines.unlink()
        amount = (self.product_id.lst_price / 100) * self.amount_percentage

        # Prepare dates if frequency based
        dates = []
        if self.contract_type == 'frequency' and self.contract_start_date and self.contract_end_date:
            start_date = fields.Date.from_string(self.contract_start_date)
            end_date = fields.Date.from_string(self.contract_end_date)
            if self.contract_frequency == 'daily':
                delta = (end_date - start_date).days + 1
                dates = [start_date + timedelta(days=i) for i in range(delta)]
            elif self.contract_frequency == 'weekly':
                delta = (end_date - start_date).days
                weeks = int(delta / 7) + 1
                dates = [start_date + timedelta(days=7 * i) for i in range(weeks)]

        serial = 1
        if self.contract_type == 'frequency' and dates:
            for date in dates:
                for _ in range(self.no_of_product):
                    self.advance_donation_lines.create({
                        'serial_no': serial,
                        'product_id': self.product_id.id,
                        'amount': amount,
                        'remaining_amount': amount,
                        'advance_donation_id': self.id,
                        'date': date,
                    })
                    serial += 1
        else:
            for i in range(self.total_no_of_product):
                self.advance_donation_lines.create({
                    'serial_no': i + 1,
                    'product_id': self.product_id.id,
                    'amount': amount,
                    'remaining_amount': amount,
                    'advance_donation_id': self.id,
                })

        self.total_product_amount = sum(line.amount for line in self.advance_donation_lines)


    @api.onchange('category_id')
    def compute_product_domain(self):
        if self.category_id:
            self.product_domain_ids = self.category_id.category_lines.product_id

    @api.onchange('donor_id')
    def onchange_donor_id(self):
        """Refresh balance when donor changes"""
        self._compute_total_balance()
        # self._compute_available_balance()

    @api.onchange('contract_start_date', 'contract_end_date', 'contract_frequency')
    def compute_no_of_days(self):
        if self.contract_start_date and self.contract_end_date and self.contract_type == 'frequency' and self.contract_frequency == 'daily':
            start_date = fields.Date.from_string(self.contract_start_date)
            end_date = fields.Date.from_string(self.contract_end_date)
            delta = end_date - start_date
            self.no_of_days = delta.days + 1
        else:
            self.no_of_days = 0

    @api.onchange('contract_start_date', 'contract_end_date', 'contract_frequency')
    def compute_no_of_weeks(self):
        if self.contract_start_date and self.contract_end_date and self.contract_type == 'frequency' and self.contract_frequency == 'weekly':
            start_date = fields.Date.from_string(self.contract_start_date)
            end_date = fields.Date.from_string(self.contract_end_date)
            delta = end_date - start_date
            self.no_of_weeks = (delta.days +1) / 7.0
        else:
            self.no_of_weeks = 0

    @api.onchange('no_of_days', 'no_of_weeks', 'no_of_product')
    def compute_total_no_of_product(self):
        if self.contract_frequency == 'weekly':
            self.total_no_of_product = self.no_of_weeks * self.no_of_product
        if self.contract_frequency == 'daily':
            self.total_no_of_product = self.no_of_days * self.no_of_product


    def action_send_for_approval(self):
        # self._validate_manual_payment()
        self.write({'state': 'approval_1'})
    
    # def _validate_manual_payment(self):
    #     """Validate that manual payment doesn't exceed available balance"""
    #     if self.manual_payment_amount > self.total_balance:
    #         raise UserError(
    #             f'Manual payment amount ({self.manual_payment_amount}) cannot be greater than '
    #             f'total available balance ({self.total_balance})'
    #         )
        
    #     if self.manual_payment_amount > self.remaining_amount:
    #         # Allow partial payment but show warning
    #         return True
    
    # def action_apply_manual_payment(self):
    #     """Apply manual payment to donation lines"""
    #     self._validate_manual_payment()
    #     if self.manual_payment_amount <= 0:
    #         raise UserError('Please enter a valid payment amount')

    #     # Get available receipts in FIFO order (oldest first)
    #     available_receipts = self.env['advance.donation.receipt'].search([
    #         ('donor_id', '=', self.donor_id.id),
    #         ('state', '=', 'paid'),
    #         ('remaining_amount', '>', 0)
    #     ], order='date asc, id asc')
    #     if not available_receipts:
    #         raise UserError('No available donation receipts found for this donor')

    #     # Apply FIFO logic to determine which receipts to use
    #     receipts_to_use = self._get_receipts_for_payment(available_receipts, self.manual_payment_amount)

    #     # Auto-attach the receipts to donation_slip_ids field
    #     current_slips = list(self.donation_slip_ids.ids)
    #     for receipt in receipts_to_use:
    #         if receipt.id not in current_slips:
    #             current_slips.append(receipt.id)

    #     # Update donation_slip_ids which will trigger onchange_donation_slip_ids automatically
    #     self.write({'donation_slip_ids': [(6, 0, current_slips)]})

        # Now reset manual_payment_amount AFTER distribution
        # self.manual_payment_amount = 0
    
    def action_refresh_balance(self):
        """Refresh total balance computation"""
        self._compute_total_balance()
        # self._compute_available_balance()
        return True

    def action_approved(self):
        if self.state == 'approval_1':
            self.write({'state': 'approval_2'})
        else:
            self.write({
                'approved_date': fields.datetime.now(),
                'state': 'approved'
            })

    def action_revert(self):
        if self.state == 'approval_1':
            if not self.approval_1_remarks:
                raise UserError('Please provide remarks')
            self.is_revert = True
            self.write({'state': 'draft'})
        if self.state == 'approval_2':
            if not self.approval_2_remarks:
                raise UserError('Please provide remarks')
            self.is_revert = True
            self.write({'state': 'approval_1'})

    def action_rejected(self):
        if self.state == 'approval_1':
            if not self.approval_1_remarks:
                raise UserError('Please provide remarks')
        if self.state == 'approval_2':
            if not self.approval_2_remarks:
                raise UserError('Please provide remarks')
        self.write({'state': 'rejected'})

    def action_cancel_payment(self):
        """Cancel payment for non-disbursed lines and return amounts to receipts"""
        self.ensure_one()
        
        # Get non-disbursed lines
        non_disbursed_lines = self.advance_donation_lines.filtered(lambda l: not l.is_disbursed)
        
        if not non_disbursed_lines:
            raise UserError('No non-disbursed lines to cancel. All lines have been disbursed.')
        
        # Calculate the amount being cancelled (returned to donor)
        cancelled_amount = sum(non_disbursed_lines.mapped('paid_amount'))
        
        # Store receipts before clearing
        old_receipts = self.donation_slip_ids
        
        # Calculate total disbursed amount BEFORE unlinking usage lines
        disbursed_lines = self.advance_donation_lines.filtered(lambda l: l.is_disbursed)
        total_disbursed_amount = sum(disbursed_lines.mapped('paid_amount')) if disbursed_lines else 0
        
        # Remove all existing usage lines
        all_usage_lines = self.donation_slip_usage_lines
        all_usage_lines.unlink()
        
        # Reset non-disbursed lines payment amounts
        for line in non_disbursed_lines:
            line.write({
                'paid_amount': 0.0,
                'remaining_amount': line.amount,
                'state': 'unpaid'
            })
        
        # Recalculate payments only for disbursed lines
        receipts_to_keep = []
        if disbursed_lines and total_disbursed_amount > 0:
            # Distribute the disbursed amount across receipts using FIFO
            # After unlinking all usage lines, all receipts have full amount available
            sorted_receipts = self.donation_slip_ids.sorted(lambda x: (x.date, x.id))
            remaining_to_allocate = total_disbursed_amount
            
            # Track how much we've allocated from each receipt in this operation
            allocated_per_receipt = {}
            
            for receipt in sorted_receipts:
                if remaining_to_allocate <= 0:
                    break
                
                # After unlink, receipt has full amount available
                # But we need to check against other donations' usage
                receipt._compute_amount()  # Force recompute after unlink
                receipt_available = receipt.amount - receipt.used_amount
                
                if receipt_available <= 0:
                    continue
                    
                allocated = min(receipt_available, remaining_to_allocate)
                
                # Keep this receipt and create usage line
                receipts_to_keep.append(receipt.id)
                self.env['advance.donation.slip.usage'].create({
                    'advance_donation_id': self.id,
                    'donation_slip_id': receipt.id,
                    'usage_amount': allocated,
                    'receipt_date': receipt.date,
                    'receipt_remaining_amount': receipt.remaining_amount
                })
                
                remaining_to_allocate -= allocated
        
        # Update donation_slip_ids to only keep receipts used by disbursed lines
        self.write({'donation_slip_ids': [(6, 0, receipts_to_keep)]})
        
        # Trigger receipt recomputation for all old receipts to update their amounts
        for receipt in old_receipts:
            receipt._compute_amount()
        
        # Force recompute of total balance
        self._compute_total_balance()
        
        # Create Customer Payment (Sent) for the cancelled amount
        if cancelled_amount > 0 and self.donor_id:
            payment_vals = {
                'payment_type': 'outbound',
                'partner_type': 'customer',
                'partner_id': self.donor_id.id,
                'amount': cancelled_amount,
                'currency_id': self.currency_id.id,
                'date': fields.Date.today(),
                'ref': f'Cancelled payment for {self.name}',
                'journal_id': self.env['account.journal'].search([
                    ('type', '=', 'bank'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1).id,
            }
            
            payment = self.env['account.payment'].create(payment_vals)
            # Optionally post the payment automatically
            # payment.action_post()
        
        # Reload the form view
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'advance.donation',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': self.env.context,
        }

    def onchange_donation_slip_ids(self,amount):
        # Reset all donation lines to unpaid state
        for rec in self.advance_donation_lines:
            rec.paid_amount = 0
            rec.remaining_amount = rec.amount

        # Use manual_payment_amount instead of total from all slips
        payment_to_distribute = amount
        remaining_value = payment_to_distribute

        # If no manual payment amount is set, don't distribute anything
        if payment_to_distribute <= 0:
            return

        # Sort donation slips by date for FIFO logic
        sorted_donation_slips = self.donation_slip_ids.sorted(lambda x: (x.date, x.id))

        for donation_slip in sorted_donation_slips:
            donation_slip_remaining_amount = donation_slip.amount - donation_slip.used_amount

            if donation_slip_remaining_amount <= 0 or remaining_value <= 0:
                continue

            for donation_line in self.advance_donation_lines:
                remaining_installment_amount = donation_line.remaining_amount
                if remaining_installment_amount <= 0:
                    continue

                if remaining_value <= 0:
                    break  # Exit the loop if there's no remaining value to distribute

                # Skip if the line is already fully paid
                if donation_line.paid_amount >= donation_line.amount:
                    continue

                # Only continue if there's still remaining amount for both the donation slip and donation line
                if donation_slip_remaining_amount <= 0:
                    continue  # Skip if this donation slip has no remaining amount to use

                # Determine how much can be paid from this donation slip
                amount_to_pay = min(remaining_installment_amount, donation_slip_remaining_amount, remaining_value)

                # Update the donation line's paid amount
                donation_line.write({
                    'paid_amount': donation_line.paid_amount + amount_to_pay,
                    'remaining_amount': donation_line.remaining_amount - amount_to_pay
                })

                # Update remaining values
                remaining_value -= amount_to_pay  # Deduct from the total remaining value
                donation_slip_remaining_amount -= amount_to_pay  # Deduct from the slip's available balance
                remaining_installment_amount -= amount_to_pay  # Deduct from the line's remaining balance

                # Create a DonationSlipUsage record to track the used amount
                self.env['advance.donation.slip.usage'].create({
                    'advance_donation_id': self.id,
                    'donation_slip_id': donation_slip.id,
                    'usage_amount': amount_to_pay,
                    'receipt_date': date.today()
                })

    def write(self, vals):
        # Only handle donation_slip_ids changes, don't unlink usage lines for other field updates
        if 'donation_slip_ids' in vals:
            # Store old receipts for recomputation
            old_donation_receipts = self.donation_slip_ids
            
            # Perform the write operation
            res = super(AdvanceDonation, self).write(vals)
            
            # Trigger receipt recomputation for old and new receipts
            for donation_slip in old_donation_receipts:
                donation_slip._compute_amount()
            
            for donation_slip in self.donation_slip_ids:
                donation_slip._compute_amount()
            
            return res
        else:
            # For other field updates, just do the normal write
            return super(AdvanceDonation, self).write(vals)
    
    def _get_receipts_for_payment(self, available_receipts, payment_amount):
        """Get receipts needed for payment using FIFO basis"""
        receipts_to_use = []
        remaining_amount = payment_amount
        
        for receipt in available_receipts:
            if remaining_amount <= 0:
                break
                
            receipt_available = receipt.remaining_amount
            if receipt_available > 0:
                receipts_to_use.append(receipt)
                remaining_amount -= receipt_available
        
        return receipts_to_use
    
    def get_used_receipts_data(self):
        """Get data for used donation receipts"""
        usage_lines = self.donation_slip_usage_lines
        return [{
            'receipt_name': line.donation_slip_id.name,
            'receipt_amount': line.donation_slip_id.amount,
            'used_amount': line.usage_amount,
            'receipt_date': line.donation_slip_id.date,
            'payment_type': line.donation_slip_id.payment_type,
        } for line in usage_lines]


    def _compute_fully_paid(self):
        paid_lines = self.advance_donation_lines.filtered(lambda line: line.state == 'paid')

        if len(paid_lines) == len(self.advance_donation_lines):
            self.is_fully_paid = True
            return {
                'domain': {
                    'donation_slip_ids': [('id', 'in', self.donation_slip_ids.ids)]
                    # Only show already selected records
                }
            }
        else:
            self.is_fully_paid = False
    
    def action_print_non_cash_report(self):
        return self.env.ref('bn_advance_donation.action_report_advance_donation_non_cash').report_action(self)
    
    def allocate_payment(self, amount, receipt_ids):
        self.ensure_one()
        if amount <= 0:
            raise UserError(_('Payment amount must be positive.'))

        unpaid_lines = self.advance_donation_lines.filtered(lambda l: l.remaining_amount > 0)
        unpaid_lines = unpaid_lines.sorted(lambda l: (l.date or fields.Date.today(), l.serial_no))
        if not unpaid_lines:
            raise UserError(_('All installments are already fully paid.'))

        receipts = self.env['advance.donation.receipt'].browse(receipt_ids).sorted(lambda r: (r.date, r.id))

        remaining_to_allocate = amount
        allocation_details = []          # list of (receipt, line, allocated_amount)
        used_receipt_ids = set()

        r_idx = 0
        l_idx = 0
        while remaining_to_allocate > 0 and r_idx < len(receipts) and l_idx < len(unpaid_lines):
            receipt = receipts[r_idx]
            line = unpaid_lines[l_idx]

            receipt_avail = receipt.remaining_amount
            line_remain = line.remaining_amount

            if receipt_avail <= 0:
                r_idx += 1
                continue
            if line_remain <= 0:
                l_idx += 1
                continue

            allocate = min(receipt_avail, line_remain, remaining_to_allocate)

            if allocate > 0:
                allocation_details.append((receipt, line, allocate))
                used_receipt_ids.add(receipt.id)
                remaining_to_allocate -= allocate

                # In‑memory updates for loop progression
                receipt.remaining_amount -= allocate
                line.remaining_amount -= allocate
                line.paid_amount += allocate

            if receipt.remaining_amount == 0:
                r_idx += 1
            if line.remaining_amount == 0:
                l_idx += 1

        # Attach only used receipts (keep existing ones)
        current_slips = self.donation_slip_ids.ids
        new_slips = list(set(current_slips) | used_receipt_ids)
        if set(new_slips) != set(current_slips):
            self.write({'donation_slip_ids': [(6, 0, new_slips)]})

        # --- GROUP ALLOCATIONS BY RECEIPT ---
        # Create one usage record per receipt with the total allocated amount
        alloc_by_receipt = {}
        for receipt, line, amount in allocation_details:
            if receipt.id not in alloc_by_receipt:
                alloc_by_receipt[receipt.id] = {'receipt': receipt, 'total': 0}
            alloc_by_receipt[receipt.id]['total'] += amount

        for receipt_id, data in alloc_by_receipt.items():
            receipt = data['receipt']
            total_alloc = data['total']
            self.env['advance.donation.slip.usage'].create({
                'advance_donation_id': self.id,
                'donation_slip_id': receipt.id,
                'usage_amount': total_alloc,
                'receipt_date': fields.Date.today(),
                'receipt_remaining_amount': receipt.remaining_amount,  # final remaining after all allocations
            })

        # Update each line (the in‑memory values are already correct)
        for receipt, line, alloc_amount in allocation_details:
            line.write({
                'paid_amount': line.paid_amount,
                'remaining_amount': line.remaining_amount,
            })

        # Force receipt fields to recompute (if they depend on a boolean trigger)
        for rid in used_receipt_ids:
            receipt = self.env['advance.donation.receipt'].browse(rid)
            receipt.write({'update_used_amount': not receipt.update_used_amount})


    def action_open_payment_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Payment',
            'res_model': 'advance.donation.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_advance_donation_id': self.id,
        }
    }