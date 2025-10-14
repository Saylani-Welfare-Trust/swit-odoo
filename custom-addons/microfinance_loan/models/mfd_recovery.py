from odoo import fields,api,models
from odoo.exceptions import UserError

class MfdRecovery(models.Model):
    _name = 'mfd.recovery'

    loan_id = fields.Many2one('mfd.loan.request', 'Load Id')
    name = fields.Char(string="Name", related='loan_id.name')
    scheme_id = fields.Many2one('mfd.scheme', string='Scheme', related='loan_id.scheme_id')
    application_id = fields.Many2one('mfd.scheme.line', string='Application For', related='loan_id.application_id')
    application_ids_domain = fields.Many2many('mfd.scheme.line', string='Application Id Domain', related='loan_id.application_ids_domain')

    asset_type = fields.Selection(
        [('cash', 'Cash'), ('movable_asset', 'Movable Asset'), ('immovable_asset', 'Immovable Asset')],
        string='Asset Type', related='loan_id.asset_type')
    customer_id = fields.Many2one('res.partner', 'Customer',related='loan_id.customer_id')
    cnic = fields.Char(string='CNIC', related='customer_id.cnic_no')
    is_employee = fields.Boolean(string='Is Employee', related='customer_id.is_employee')
    product_id = fields.Many2one('product.product', string='Asset', related='loan_id.product_id')
    product_ids_domain = fields.Many2many('product.product', string='Product Domain', related='loan_id.product_ids_domain')

    currency_id = fields.Many2one('res.currency', 'Currency', related='loan_id.currency_id')
    amount = fields.Monetary('Amount', currency_field='currency_id', related='loan_id.amount')
    security_deposit = fields.Monetary('Security Deposit', currency_field='currency_id', related='loan_id.security_deposit')
    donor_contribution = fields.Monetary('Contribution by Donor', currency_field='currency_id', related='loan_id.donor_contribution')
    total_amount = fields.Monetary('Total Amount', currency_field='currency_id', related='loan_id.total_amount')
    disbursement_date = fields.Date('Delivery Date', related='loan_id.disbursement_date')
    installment_type = fields.Selection([('daily', 'Daily'), ('monthly', 'Monthly')], string='Installment Type',
                                        default='daily', related='loan_id.installment_type')
    installment_amount = fields.Monetary('Installment Amount', currency_field='currency_id', related='loan_id.installment_amount')
    installment_period = fields.Integer('Installment Period', related='loan_id.installment_period')
    asset_availability = fields.Selection([('not_available', 'Not Available'), ('available', 'Available')], string='Asset Availability')
    warehouse_loc_id = fields.Many2one('stock.location', 'Warehouse/Location', related='loan_id.warehouse_loc_id')
    recovery_request_lines = fields.One2many('mfd.recovery.line', 'recovery_id')
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

    attachment_id = fields.Binary(string="Attach Form")
    attachment_name = fields.Char()
    hod_remarks = fields.Html(string="HOD Remarks")
    mem_remarks = fields.Html(string="Member Remarks")
    initiate_recovery = fields.Boolean()
    remaining_amount = fields.Monetary('Remaining Amount', currency_field='currency_id', compute='_compute_amount')
    paid_amount = fields.Monetary('Paid Amount', currency_field='currency_id')
    installment_paid_amount = fields.Monetary('Paid Amount', currency_field='currency_id', compute='_compute_amount')

    recovered_location_id = fields.Many2one('stock.location', 'Destination Location')
    recovered_product_id = fields.Many2one('product.product', 'Recovered Product')
    remarks = fields.Html(string='Remarks')
    member_right_of_remarks = fields.Html(string='Member Remarks')
    cfo_right_of_remarks = fields.Html(string='CFO Remarks')

    pdc_attachment_id = fields.Binary(string="Attach PDCs")
    pdc_attachment_name = fields.Char()
    is_revert = fields.Boolean()
    is_sec_dep_paid = fields.Boolean()
    sd_slip_id = fields.Many2one('mfd.installment.receipt', 'SD Slip')


    def _compute_amount(self):
        for rec in self:
            installment_ids = self.env['mfd.loan.request.line'].search([
                ('loan_request_id', '=', rec.loan_id.id)
            ])
            unpaid_filtered_installments = installment_ids.filtered(lambda r: r.state != 'paid')
            total_remaining_amount = sum(unpaid_filtered_installments.mapped('remaining_amount'))

            paid_filtered_installments = installment_ids.filtered(lambda r: r.state in ('paid','partial'))
            total_paid_amount = sum(paid_filtered_installments.mapped('paid_amount'))

            rec.remaining_amount = total_remaining_amount
            rec.paid_amount = total_paid_amount

    def action_temp_recovered(self):
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
                    'default_recovery_id': self.id,
                    'default_partner_id': self.customer_id.id,
                    'default_product_ids_domain': product_line.recover_product_id.ids,
                    'default_source_document': self.name,
                    'default_loan_id': self.loan_id.id
                }
            return action
        else:
            self.write({'state': 'recovered'})

    def action_fully_recovered(self):
        self.loan_id.write({'state': 'fully_recovered'})
        self.write({'state': 'fully_recovered'})


    def action_move_to_done(self):
        if self.asset_type == 'movable_asset':
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

        self.loan_id.write({'state': 'done'})
        self.write({'state': 'done'})


    def request_write_off(self):
        if not self.remarks:
            raise UserError('Please provide remarks')
        self.member_right_of_remarks = False
        self.cfo_right_of_remarks = False
        self.loan_id.write({'state': 'right_of_approval'})
        self.write({'state': 'right_of_approval'})


    def action_right_of_granted(self):
        if self.state == 'right_of_approval':
            self.loan_id.write({'state': 'right_of_approval_2'})
            self.write({'state': 'right_of_approval_2'})
        else:
            self.loan_id.write({'state': 'right_of_granted'})
            self.write({'state': 'right_of_granted'})

    def action_right_of_rejected(self):
        if self.state == 'right_of_approval':
            if not self.member_right_of_remarks:
                raise UserError('Please provide remarks')
        if self.state == 'right_of_approval_2':
            if not self.cfo_right_of_remarks:
                raise UserError('Please provide remarks')
        self.remarks = False
        self.loan_id.write({'state': 'fully_recovered'})
        self.write({'state': 'fully_recovered'})




class MfdRecoveryLine(models.Model):
    _name = 'mfd.recovery.line'

    recovery_id = fields.Many2one('mfd.recovery', string='Recovery Id', required=True, ondelete='cascade')
    loan_state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'HOD Approval'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('rejected', 'Rejected')], related='recovery_id.state')
    installment_number = fields.Integer('Installment Number', required=True)
    installment_id = fields.Char('Installment Id', required=True)
    due_date = fields.Date('Due Date', required=True)
    amount = fields.Monetary('Amount', currency_field='currency_id')
    paid_amount = fields.Monetary('Paid Amount', currency_field='currency_id')
    remaining_amount = fields.Monetary('Remaining Amount', currency_field='currency_id',
                                       compute='_compute_remaining_amount')
    currency_id = fields.Many2one('res.currency', 'Currency', related='recovery_id.currency_id', readonly=True)
    is_cheque_deposit = fields.Boolean()
    state = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid')],
        string='Status', compute='_compute_installment_state',
        help=" * Unpaid: The installment is not paid yet.\n * Paid: The installment is paid.\n * Overdue: The installment is overdue.")
    # payment_id = fields.Many2one('mfd.installment.receipt', string='Payment ID')
    # is_payment_done = fields.Boolean(compute='_compute_check_payment_id')

    cheque_no = fields.Char('Cheque Number')
    mfd_bank_id = fields.Many2one('mfd.bank', 'Bank Name')
    cheque_amount = fields.Monetary('Amount', currency_field='currency_id')
    cheque_date = fields.Date('Cheque Date')

    def _compute_installment_state(self):
        for rec in self:
            if rec.paid_amount < rec.amount and rec.paid_amount != 0:
                rec.state = 'partial'
            elif rec.paid_amount == rec.amount:
                rec.state = 'paid'
            else:
                rec.state = 'unpaid'

    def _compute_remaining_amount(self):
        for rec in self:
            rec.remaining_amount = rec.amount - rec.paid_amount
