from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError
from datetime import timedelta

from .res_partner_category import donor_account_domain

STATE_LABELS = {
    'draft': 'Draft', 'approval_1': 'Approval 1', 'approval_2': 'Approval 2',
    'approved': 'Approved', 'rejected': 'Rejected',
}
APPROVAL_GROUPS = {
    'approval_1': 'bn_advance_donation.group_adv_don_approval_1',
    'approval_2': 'bn_advance_donation.group_adv_don_approval_2',
}

# The terms of a donation: set in Draft, fixed once it is sent for approval
# (what the approvers approved is what is paid and disbursed)
TERM_FIELDS = {
    'donor_id', 'category_id', 'contract_type', 'payment_type', 'total_no_of_product',
    'contract_frequency', 'product_id', 'amount_percentage', 'no_of_product',
    'contract_start_date', 'contract_end_date', 'no_of_days', 'no_of_weeks',
    'service_charges', 'service_charge_product_id', 'service_charge_amount',
}


def changed_fields(record, vals, names):
    """The fields of ``names`` that ``vals`` really changes on ``record``."""
    changed = set()
    for name in names & set(vals):
        field = record._fields[name]
        new = vals[name]
        old = record[name].id if field.type == 'many2one' else record[name]
        if field.type == 'many2one':
            new = new or False
        if (old or False) != (new or False):
            changed.add(name)
    return changed


# An open contract is one amount: no frequency, no date range
OPEN_CONTRACT_EMPTY = {
    'contract_frequency': False,
    'contract_start_date': False,
    'contract_end_date': False,
    'no_of_days': 0,
    'no_of_weeks': 0,
}


class AdvanceDonation(models.Model):
    _name = 'advance.donation'
    _description = "Advance Donation"
    _inherit = ['step.activity.mixin', 'mail.thread', 'mail.activity.mixin']
    # _table = 'advance_donation_new'   

    name = fields.Char(string="Name", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    # only donors registered for Advance Donation (Record Search > Donor Account)
    donor_id = fields.Many2one(
        'res.partner', 
        string='Donor',
        domain=donor_account_domain,
    )
    category_id = fields.Many2one('advance.donation.category', string='Category')
    contract_type = fields.Selection([('product', 'Quantity Based'),
                                     ('frequency', 'Frequency Based'),
                                     ('open_contract', 'Open Contract')],
                                    string='Contract Type', default='product')

    payment_type = fields.Selection([('cash', 'Cash'),
                                    ('credit', 'Credit')],
                                   string='Payment Type', default='cash')

    total_no_of_product = fields.Integer('Total No of Products')
    donation_slip_ids = fields.Many2many('advance.donation.receipt', 'rel_2', string='Donation Slip', copy=False)

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
    approval_1_remarks = fields.Html(string='Approval (1) Remarks')
    approval_2_remarks = fields.Html(string='Approval (2) Remarks')

    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)
    total_product_amount = fields.Monetary('Total Amount', currency_field='currency_id')
    paid_amount = fields.Monetary('Paid Amount', compute='_compute_amount')
    remaining_amount = fields.Monetary('Remaining Amount', compute='_compute_amount')
    
    # New fields for balance management
    total_balance = fields.Monetary('Total Balance', currency_field='currency_id', compute='_compute_total_balance', store=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approval_1', 'Approval 1'),
        ('approval_2', 'Approval 2'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')],
        default='draft',
        string='Status')

    advance_donation_lines = fields.One2many('advance.donation.lines', 'advance_donation_id')
    donation_slip_usage_lines = fields.One2many('advance.donation.slip.usage', 'advance_donation_id')

    approved_date = fields.Datetime('Approved Date')
    is_fully_paid = fields.Boolean(compute='_compute_fully_paid')
    is_fully_disbursed = fields.Boolean(compute='_compute_fully_disbursed', store=True)
    
    disbursement_line_ids = fields.One2many(
        'advance.donation.disbursement.line',
        'advance_donation_id',
        string="Disbursement Lines"
    )
    service_charges = fields.Boolean(string="Service Charges", default=False)
    service_charge_product_id = fields.Many2one(
        'product.product',
        string='Service Charge Product',
        domain=[('is_service_charge', '=', True)]
    )
    service_charge_amount = fields.Monetary(
        string='Service Charge Amount',
        currency_field='currency_id'
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('advance.donation') or _('New')
            if vals.get('contract_type') == 'open_contract':
                vals.update(OPEN_CONTRACT_EMPTY)
        records = super().create(vals_list)
        records.filtered('donation_slip_ids')._check_slip_allowed()
        return records

    # ------------------------------------------------------------------
    # Workflow checks
    # ------------------------------------------------------------------
    def _check_slip_allowed(self):
        """Donation slips (receipts) are used only on an approved donation."""
        self._check_donation_state(('approved',), _('Add Donation Slip'))

    def _check_donation_state(self, allowed, action):
        for rec in self:
            if rec.state not in allowed:
                raise UserError(_('"%(action)s" is not possible for %(name)s in status "%(state)s".') % {
                    'action': action, 'name': rec.name, 'state': STATE_LABELS.get(rec.state, rec.state)})

    def _check_approver(self, action):
        """The approver of the current approval step decides."""
        self._check_donation_state(('approval_1', 'approval_2'), action)
        for rec in self:
            if not self.env.su and not self.env.user.has_group(APPROVAL_GROUPS[rec.state]):
                raise AccessError(_('Only %(step)s approvers can do "%(action)s" on %(name)s.') % {
                    'step': STATE_LABELS[rec.state], 'action': action, 'name': rec.name})

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
        for rec in self:
            lines = rec.advance_donation_lines
            rec.is_fully_disbursed = bool(lines) and all(lines.mapped('is_disbursed'))
    
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
    
    
    @api.onchange('contract_type')
    def _onchange_contract_type(self):
        if self.contract_type == 'open_contract':
            self.total_no_of_product = 1
            self.no_of_product = 1   # also for consistency
            self.amount_percentage = 100.00
            self.update(OPEN_CONTRACT_EMPTY)
        elif self.contract_type == 'frequency' and not self.contract_frequency:
            self.contract_frequency = 'daily'
    @api.onchange('service_charges')
    def _onchange_service_charges(self):
        if not self.service_charges:
            self.service_charge_product_id = False
            self.service_charge_amount = 0.0

    @api.onchange('service_charge_product_id')
    def _onchange_service_charge_product_id(self):
        self.service_charge_amount = (
            self.service_charge_product_id.lst_price
            if self.service_charge_product_id else 0.0
        )

    def compute_donation(self):
        self.ensure_one()
        self._check_donation_state(('draft',), _('Compute Donation'))
        if any(self.advance_donation_lines.mapped('paid_amount')) or self.advance_donation_lines.filtered('is_disbursed'):
            raise UserError(_('%s already has payments or disbursements: cancel the payments before computing the lines again.') % self.name)
        self.advance_donation_lines.unlink()
        amount = (self.product_id.lst_price / 100) * self.amount_percentage
        unit_service_charge = self.service_charge_amount or 0.0 if self.service_charges else 0.0

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
        line_service_charge = unit_service_charge if self.service_charges else 0.0
        total_lines = 0

        if self.contract_type == 'frequency' and dates:
            # One consolidated line per day (or week) for all the products of that day
            if self.no_of_product > 0:
                for line_date in dates:
                    self.advance_donation_lines.create({
                        'serial_no': serial,
                        'product_id': self.product_id.id,
                        'quantity': self.no_of_product,
                        'amount': amount * self.no_of_product,
                        'service_charge_amount': line_service_charge * self.no_of_product,
                        'remaining_amount': (amount + line_service_charge) * self.no_of_product,
                        'advance_donation_id': self.id,
                        'date': line_date,
                    })
                    serial += 1
                    total_lines += 1
        else:
            # Lines that are not spread over days are dated the day they are computed
            today = fields.Date.context_today(self)
            if self.contract_type != 'open_contract':
                for i in range(self.total_no_of_product):
                    self.advance_donation_lines.create({
                        'serial_no': i + 1,
                        'product_id': self.product_id.id,
                        'amount': amount,
                        'service_charge_amount': line_service_charge,
                        'remaining_amount': amount + line_service_charge,
                        'advance_donation_id': self.id,
                        'date': today,
                    })
                    total_lines += 1
            else:
                self.advance_donation_lines.create({
                    'serial_no': 1,
                    'product_id': self.product_id.id,
                    'amount': self.total_product_amount,
                    'service_charge_amount': line_service_charge,
                    'remaining_amount': self.total_product_amount + line_service_charge,
                    'advance_donation_id': self.id,
                    'date': today,
                })
                total_lines = 1

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
        self._check_donation_state(('draft',), _('Send for Approval'))
        for rec in self:
            if not rec.advance_donation_lines:
                raise UserError(_('Compute the donation lines of %s before sending it for approval.') % rec.name)
        self.write({'state': 'approval_1'})
    
        # Now reset manual_payment_amount AFTER distribution
    
    def action_refresh_balance(self):
        """Refresh total balance computation"""
        self._compute_total_balance()
        # self._compute_available_balance()
        return True

    def action_approved(self):
        self._check_approver(_('Approve'))
        for rec in self:
            if rec.state == 'approval_1':
                rec.write({'state': 'approval_2'})
            else:
                rec.write({'approved_date': fields.Datetime.now(), 'state': 'approved'})

    def _check_remarks(self):
        for rec in self:
            if not (rec.approval_1_remarks if rec.state == 'approval_1' else rec.approval_2_remarks):
                raise UserError(_('Please provide remarks'))

    def action_revert(self):
        self._check_approver(_('Revert'))
        self._check_remarks()
        for rec in self:
            rec.write({'is_revert': True, 'state': 'draft' if rec.state == 'approval_1' else 'approval_1'})

    def action_rejected(self):
        self._check_approver(_('Reject'))
        self._check_remarks()
        self.write({'state': 'rejected'})

    def action_cancel_payment(self):
        """Cancel payment for non-disbursed lines and return amounts to receipts"""
        self.ensure_one()
        self._check_donation_state(('draft', 'approval_1', 'approval_2', 'approved'), _('Cancel Payment'))
        
        # A line of which anything was disbursed keeps its payment: refunding it
        # would give the disbursed part out a second time
        def used(line):
            return line.is_disbursed or line.disbursed_amount > 0
        non_disbursed_lines = self.advance_donation_lines.filtered(lambda l: not used(l))

        if not non_disbursed_lines:
            raise UserError('No non-disbursed lines to cancel. All lines have been disbursed.')
        
        # Calculate the amount being cancelled (returned to donor)
        cancelled_amount = sum(non_disbursed_lines.mapped('paid_amount'))
        
        # Store receipts before clearing
        old_receipts = self.donation_slip_ids
        
        # Calculate total disbursed amount BEFORE unlinking usage lines
        disbursed_lines = self.advance_donation_lines.filtered(used)
        total_disbursed_amount = sum(disbursed_lines.mapped('paid_amount')) if disbursed_lines else 0
        
        # Remove all existing usage lines
        all_usage_lines = self.donation_slip_usage_lines
        all_usage_lines.unlink()
        
        # Reset non-disbursed lines payment amounts
        for line in non_disbursed_lines:
            line.write({
                'paid_amount': 0.0,
                'remaining_amount': line.amount + line.service_charge_amount,
                'state': 'unpaid'
            })
        
        # Recalculate payments only for disbursed lines
        receipts_to_keep = []
        if disbursed_lines and total_disbursed_amount > 0:
            # Distribute the disbursed amount across receipts using FIFO
            # After unlinking all usage lines, all receipts have full amount available
            sorted_receipts = self.donation_slip_ids.sorted(lambda x: (x.date, x.id))
            remaining_to_allocate = total_disbursed_amount
            
            
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
            
            self.env['account.payment'].create(payment_vals)
        
        # Reload the form view
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'advance.donation',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': self.env.context,
        }

    def write(self, vals):
        if not self.env.su:
            for rec in self.filtered(lambda r: r.state != 'draft'):
                changed = changed_fields(rec, vals, TERM_FIELDS)
                if changed:
                    raise UserError(_('The terms of %(name)s can only be changed in Draft (status: %(state)s). '
                                      'Changed: %(fields)s.') % {
                        'name': rec.name, 'state': STATE_LABELS.get(rec.state, rec.state),
                        'fields': ', '.join(sorted(rec._fields[f].string for f in changed))})
        if vals.get('contract_type') == 'open_contract':
            vals = dict(vals, **OPEN_CONTRACT_EMPTY)
        # Only handle donation_slip_ids changes, don't unlink usage lines for other field updates
        if 'donation_slip_ids' in vals:
            # Store old receipts for recomputation
            old_donation_receipts = self.donation_slip_ids
            old_slips = {rec.id: rec.donation_slip_ids for rec in self}

            # Perform the write operation
            res = super(AdvanceDonation, self).write(vals)

            # A slip can be added only once the donation is approved; removing
            # slips (Cancel Payment) stays possible in every state.
            self.filtered(lambda rec: rec.donation_slip_ids - old_slips[rec.id])._check_slip_allowed()

            # Trigger receipt recomputation for old and new receipts
            for donation_slip in old_donation_receipts:
                donation_slip._compute_amount()
            
            for donation_slip in self.donation_slip_ids:
                donation_slip._compute_amount()
            
            return res
        else:
            # For other field updates, just do the normal write
            return super(AdvanceDonation, self).write(vals)
    
    def _compute_fully_paid(self):
        for rec in self:
            lines = rec.advance_donation_lines
            rec.is_fully_paid = bool(lines) and all(state == 'paid' for state in lines.mapped('state'))
    
    def action_print_non_cash_report(self):
        return self.env.ref('bn_advance_donation.action_report_advance_donation_non_cash').report_action(self)
    
    def allocate_payment(self, amount, receipt_ids):
        self.ensure_one()
        self._check_donation_state(('approved',), _('Add Payment'))
        if amount <= 0:
            raise UserError(_('Payment amount must be positive.'))
        foreign = self.env['advance.donation.receipt'].browse(receipt_ids).filtered(
            lambda r: r.donor_id != self.donor_id or r.state != 'paid')
        if foreign:
            raise UserError(_('Only paid receipts of the donor %(donor)s can be used (not %(receipts)s).') % {
                'donor': self.donor_id.display_name, 'receipts': ', '.join(foreign.mapped('name'))})

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
        self._check_donation_state(('approved',), _('Add Payment'))
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