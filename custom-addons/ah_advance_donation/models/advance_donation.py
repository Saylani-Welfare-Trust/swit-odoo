from odoo import fields,api,models,_
from odoo.exceptions import UserError

class AdvanceDonation(models.Model):
    _name = 'ah.advance.donation'

    name = fields.Char(string="Name", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    customer_id = fields.Many2one('adv.don.customer', string='Customer')
    category_id = fields.Many2one('adv.don.category', string='Category')
    contract_type = fields.Selection([('product', 'Quantity Based'),
                                     ('frequency', 'Frequency Based')],
                                    string='Contract Type', default='product')

    payment_type = fields.Selection([('cash', 'Cash'),
                                    ('credit', 'Credit')],
                                   string='Payment Type', default='cash')

    total_no_of_product = fields.Integer('Total No of Products')
    # donation_slip_domain_ids = fields.Many2many('ah.advance.donation.receipt', 'rel_1', string='Donation')
    donation_slip_ids = fields.Many2many('ah.advance.donation.receipt', 'rel_2', string='Donation Slip')

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

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approval_1', 'Approval 1'),
        ('approval_2', 'Approval 2'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')],
        default='draft',
        string='Status')

    advance_donation_lines = fields.One2many('ah.advance.donation.line', 'advance_donation_id')
    donation_slip_usage_lines = fields.One2many('advance.donation.slip.usage', 'advance_donation_id')

    approved_date = fields.Datetime('Approved Date')
    is_fully_paid = fields.Boolean(compute='_compute_fully_paid')
    is_fully_disbursed = fields.Boolean(compute='_compute_fully_disbursed', store=True)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('ah.advance.donation') or ('New')
        return super().create(vals)

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


    # @api.onchange('customer_id')
    # def domain_donation_slip_ids(self):
    #     for rec in self:
    #         rec.donation_slip_domain_ids = False
    #         rec.donation_slip_ids = False
    #         domain = ([
    #             ('state', '=', 'paid'),
    #             ('partner_id', '=', rec.customer_id.id),
    #             ('is_remaining_amount', '=', True),
    #         ])
    #         if rec.is_fully_paid == True:
    #             domain += [('id', 'in', rec.donation_slip_ids.ids)]
    #
    #         donation_slip_ids = self.env['ah.advance.donation.receipt'].search(domain)
    #         print('donation_slip_ids', donation_slip_ids)
    #         rec.donation_slip_domain_ids = donation_slip_ids.ids

    def compute_donation(self):
        self.advance_donation_lines.unlink()
        amount = (self.product_id.lst_price / 100) * self.amount_percentage

        for i in range(self.total_no_of_product):
            self.advance_donation_lines.create({
                'serial_no': i+1,
                'product_id': self.product_id.id,
                'amount': amount,
                'remaining_amount': amount,
                'advance_donation_id': self.id
            })

        self.total_product_amount = sum(line.amount for line in self.advance_donation_lines)


    @api.onchange('category_id')
    def compute_product_domain(self):
        if self.category_id:
            self.product_domain_ids = self.category_id.category_lines.product_id

    # @api.onchange('customer_id')
    # def compute_donation_ids_domain(self):
    #     self.donation_slip_ids = False
    #     if self.customer_id:
    #         donation_receipts = self.env['ah.advance.donation.receipt'].search([
    #             ('partner_id', '=', self.customer_id.id),
    #             ('state', '=', 'paid')
    #         ])
    #         self.donation_slip_domain = donation_receipts

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
        self.write({'state': 'approval_1'})

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


    def onchange_donation_slip_ids(self):
        for rec in self.advance_donation_lines:
            rec.paid_amount = 0
            rec.remaining_amount = rec.amount

        # self.donation_slip_usage_lines.unlink()

        total_paid_from_slips = sum(self.donation_slip_ids.mapped('amount'))
        remaining_value = total_paid_from_slips

        for donation_slip in self.donation_slip_ids:
            donation_slip_remaining_amount = donation_slip.amount - donation_slip.used_amount

            if donation_slip_remaining_amount <= 0 or remaining_value <= 0:
                continue

            # deleted_records = self.donation_slip_usage_lines.search([('donation_slip_id', '=', donation_slip.id)])
            # deleted_records.unlink()

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
                })



    # total_paid_from_slips = sum(self.donation_slip_ids.mapped('amount'))
        # remaining_value = total_paid_from_slips
        #
        # for donation_line in self.advance_donation_lines:
        #     if remaining_value <= 0:
        #         break
        #
        #     remaining_installment_amount = donation_line.remaining_amount
        #
        #     if remaining_installment_amount <= remaining_value:
        #         donation_line.write({
        #             'paid_amount': donation_line.amount,
        #         })
        #         remaining_value -= remaining_installment_amount
        #     else:
        #         donation_line.write({
        #             'paid_amount': donation_line.paid_amount + remaining_value
        #         })
        #         remaining_value = 0

    def write(self, vals):
        self.donation_slip_usage_lines.unlink()
        old_donation_receipts = self.donation_slip_ids
        for donation_slip in old_donation_receipts:
           if donation_slip.update_used_amount:
               donation_slip.write({'update_used_amount': False})
           else:
               donation_slip.write({'update_used_amount': True})



        res = super(AdvanceDonation, self).write(vals)

        self.onchange_donation_slip_ids()


        for donation_slip in old_donation_receipts:
           if donation_slip.update_used_amount:
               donation_slip.write({'update_used_amount': False})
           else:
               donation_slip.write({'update_used_amount': True})

        for donation_slip in self.donation_slip_ids:
           if donation_slip.update_used_amount:
               donation_slip.write({'update_used_amount': False})
           else:
               donation_slip.write({'update_used_amount': True})



        return res


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

    # @api.ondelete(at_uninstall=False)
    # def restrict_delete(self):
    #     for rec in self:
    #         if rec.state != 'draft':
    #             raise UserError(f'You cannot delete record in {rec.state} state')


    # ------------POS Functions----------------

    @api.model
    def check_bank_ids(self):
        bank_ids = self.env['config.bank'].search([])
        return {
            "status": "success",
            'bank_ids': [{'id': bank.id, 'name': bank.name} for bank in bank_ids]
        }





