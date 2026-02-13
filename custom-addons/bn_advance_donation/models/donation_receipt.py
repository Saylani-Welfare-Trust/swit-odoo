from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)


class DonationReceipt(models.Model):
    _name = 'advance.donation.receipt'


    name = fields.Char(string="Name", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    payment_type = fields.Selection([('cash', 'Cash'), ('cheque', 'Cheque')], string='Payment Method', default='cash')
    is_donation_id = fields.Boolean('Donation ID?')
    donation_id = fields.Many2one('advance.donation', string='Donation ID')
    order_id = fields.Many2one('pos.order', string='POS Order')
    donor_id = fields.Many2one('res.partner', string='Donor')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)
    amount = fields.Monetary('Amount', currency_field='currency_id')
    used_amount = fields.Monetary('Used Amount', currency_field='currency_id', default=0, compute='_compute_amount', store=True)
    remaining_amount = fields.Monetary('Remaining Amount', currency_field='currency_id', compute='_compute_amount', store=True)
    update_used_amount = fields.Boolean('Update')
    date = fields.Date(string='Date', default=fields.Date.today())
    product_id = fields.Many2one('product.product', string='Product')
    cheque_number = fields.Char(string='Cheque Number')
    cheque_date = fields.Date(string='Cheque Date')
    bounced_reason = fields.Html(string='Reason')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('bounced', 'Bounced')],
        string='Status',
        default='draft')
    bank_id = fields.Many2one('bank', string='Bank')
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('advance.donation.receipt') or ('New')
        return super().create(vals)

    @api.onchange('donation_id')
    def onchange_donation_id(self):
        if self.donation_id:
            self.donor_id = self.donation_id.donor_id.id # type: ignore

    @api.onchange('is_donation_id')
    def onchange_is_donation_id(self):
        self.donation_id = False


    def action_pending(self):
        if self.product_id:
            credit_account = self.product_id.categ_id.property_account_income_categ_id or self.product_id.property_account_income_id
            debit_account = self.product_id.categ_id.property_account_expense_categ_id or self.product_id.property_account_expense_id
        else:
            raise UserError('No product selected for account determination.')

        if not credit_account:
            raise UserError('No Credit Account found on product or category.')
        if not debit_account:
            raise UserError('No Debit Account found on product or category.')
        
        if self.payment_type == 'cheque':
                # credit_account = self.env.ref('bn_advance_donation.cheque_deposit_credit_account_first').account_id
                # debit_account = self.env.ref('bn_advance_donation.cheque_deposit_debit_account_first').account_id

            move_lines = [
                {
                    'name': f'{self.name}',
                    'account_id': credit_account.id,
                    'credit': self.amount,
                    'debit': 0.0,
                    'partner_id': self.donor_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                },
                {
                    'name': f'{self.name}',
                    'account_id': debit_account.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': self.donor_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                }
            ]
            move = self.env['account.move'].create({
                'ref': f'{self.name}',
                'partner_id': self.donor_id.id,
                'line_ids': [(0, 0, line) for line in move_lines],
                'date': fields.Date.today(),
                'move_type': 'entry',
            })
            move.action_post()

            # credit_account = self.env.ref('bn_advance_donation.cheque_deposit_credit_account_second').account_id
            # debit_account = self.env.ref('bn_advance_donation.cheque_deposit_debit_account_second').account_id

            if not credit_account:
                raise UserError('No Credit Account found')
            if not debit_account:
                raise UserError('No Debit Account found')

            move_lines = [
                {
                    'name': f'{self.name}',
                    'account_id': credit_account.id,
                    'credit': self.amount,
                    'debit': 0.0,
                    'partner_id': self.donor_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                },
                {
                    'name': f'{self.name}',
                    'account_id': debit_account.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': self.donor_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                }
            ]
            move = self.env['account.move'].create({
                'ref': f'{self.name}',
                'partner_id': self.donor_id.id,
                'line_ids': [(0, 0, line) for line in move_lines],
                'date': fields.Date.today(),
                'move_type': 'entry',
            })
            move.action_post()

        self.write({'state': 'paid'})


    def action_bounced(self):
        if not self.bounced_reason:
            raise UserError('Please provide reason')
        self.write({'state': 'bounced'})


    def action_paid(self):
        if self.product_id:
            credit_account = self.product_id.categ_id.property_account_income_categ_id or self.product_id.property_account_income_id
            debit_account = self.product_id.categ_id.property_account_expense_categ_id or self.product_id.property_account_expense_id
        else:
            raise UserError('No product selected for account determination.')

        if not credit_account:
            raise UserError('No Credit Account found on product or category.')
        if not debit_account:
            raise UserError('No Debit Account found on product or category.')
        
        if self.donation_id:
            donation_lines = self.donation_id.advance_donation_lines
            unpaid_donation_lines = donation_lines.filtered(lambda r: r.state != 'paid')
            total_remaining_amount = sum(unpaid_donation_lines.mapped('remaining_amount'))

            if self.amount > total_remaining_amount:
                raise UserError(
                    f'You cannot pay more than the remaining amount. Remaining Amount: {total_remaining_amount}')
            self.donation_id.donation_slip_ids = [(4, self.id)]

        if self.payment_type == 'cash':
            # credit_account = self.env.ref('bn_advance_donation.cash_payment_credit_account').account_id
            # debit_account = self.env.ref('bn_advance_donation.cash_payment_debit_account').account_id

            # if not credit_account:
            #     raise UserError('No Credit Account found')
            # if not debit_account:
            #     raise UserError('No Debit Account found')

            move_lines = [
                {
                    'name': f'{self.name}',
                    'account_id': credit_account.id,
                    'credit': self.amount,
                    'debit': 0.0,
                    'partner_id': self.donor_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                },
                {
                    'name': f'{self.name}',
                    'account_id': debit_account.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': self.donor_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                }
            ]
            move = self.env['account.move'].create({
                'ref': f'{self.name}',
                'partner_id': self.donor_id.id,
                'line_ids': [(0, 0, line) for line in move_lines],
                'date': fields.Date.today(),
                'move_type': 'entry',
            })

            move.action_post()

        if self.payment_type == 'cheque':
            # credit_account = self.env.ref('bn_advance_donation.cheque_payment_credit_account_first').account_id
            # debit_account = self.env.ref('bn_advance_donation.cheque_payment_debit_account_first').account_id

            move_lines = [
                {
                    'name': f'{self.name}',
                    'account_id': credit_account.id,
                    'credit': self.amount,
                    'debit': 0.0,
                    'partner_id': self.donor_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                },
                {
                    'name': f'{self.name}',
                    'account_id': debit_account.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': self.donor_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                }
            ]
            move = self.env['account.move'].create({
                'ref': f'{self.name}',
                'partner_id': self.donor_id.id,
                'line_ids': [(0, 0, line) for line in move_lines],
                'date': fields.Date.today(),
                'move_type': 'entry',
            })
            move.action_post()

            # credit_account = self.env.ref('bn_advance_donation.cheque_payment_credit_account_second').account_id
            # debit_account = self.env.ref('bn_advance_donation.cheque_payment_debit_account_second').account_id

            move_lines = [
                {
                    'name': f'{self.name}',
                    'account_id': credit_account.id,
                    'credit': self.amount,
                    'debit': 0.0,
                    'partner_id': self.donor_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                },
                {
                    'name': f'{self.name}',
                    'account_id': debit_account.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': self.donor_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                }
            ]
            move = self.env['account.move'].create({
                'ref': f'{self.name}',
                'partner_id': self.donor_id.id,
                'line_ids': [(0, 0, line) for line in move_lines],
                'date': fields.Date.today(),
                'move_type': 'entry',
            })
            move.action_post()

        self.write({'state': 'paid'})


    def action_redeposit_cheque(self):
        action = self.env.ref('bn_advance_donation.action_advance_donation_receipt').read()[0]
        form_view_id = self.env.ref('bn_advance_donation.view_advance_donation_receipt_form').id
        action['views'] = [
            [form_view_id, 'form']
        ]
        action['context'] = {
            'default_loan_id': self.donation_id.id,
            # 'default_partner_id': self.partner_id.id,
            'default_donor_id': self.donor_id.id,
            'default_amount': self.amount,
            'default_payment_type': self.payment_type,
            'default_currency_id': self.currency_id.id,
            'default_mfd_bank_id': self.bank_id.id,
            'default_cheque_number': self.cheque_number,
            'default_cheque_date': self.cheque_date
        }
        return action

    @api.depends('update_used_amount')
    def _compute_amount(self):
        for rec in self:
            donation_slip_usage_lines = self.env['advance.donation.slip.usage'].search([
                ('donation_slip_id', '=', rec.id)
            ])
            rec.used_amount = sum(donation_slip_usage_lines.mapped('usage_amount'))
            rec.remaining_amount = rec.amount - rec.used_amount


    @api.ondelete(at_uninstall=False)
    def restrict_delete(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(f'You cannot delete record in {rec.state} state')


    # ------------POS Functions----------------
    @api.model
    def register_pos_payment(self, data):
        _logger.info(f"Registering POS payment with data: {data}")
        
        try:
            # # Find POS order by order_name
            pos_order = None
            # if data.get('order_name'):
            #     _logger.info(f"Searching for POS order: {data['order_name']}")
            #     pos_order = self.env['pos.order'].sudo().search([('pos_reference', '=', data['order_name'])], limit=1)
                
            #     if not pos_order:
            #         _logger.error(f"POS Order not found: {data['order_name']}")
            #         return {
            #             "status": "error",
            #             "body": "POS Order not found",
            #         }
                
            #     _logger.info(f"Found POS order: {pos_order.id} - {pos_order.name}")

            # if not data['amount']:
            #     return {
            #         "status": "error",
            #         "body": "Please enter amount",
            #     }

            # Convert amount to float and get absolute value
            try:
                amount = abs(float(data['amount']))
                _logger.info(f"Processing amount: {data['amount']} -> {amount}")
            except (ValueError, TypeError):
                return {
                    "status": "error",
                    "body": "Invalid amount format",
                }

            if data['payment_type'] == 'cheque':
                if not data['bank_id']:
                    return {
                        "status": "error",
                        "body": "Please select bank",
                    }
                if not data['cheque_number']:
                    return {
                        "status": "error",
                        "body": "Please enter cheque number",
                    }
                if not data['cheque_date']:
                    return {
                        "status": "error",
                        "body": "Please enter cheque date",
                    }
            
            _logger.info("Creating donation receipt...")
            
            # Create payment with positive amount
            payment_vals = {
                'payment_type': data['payment_type'],
                'is_donation_id': data.get('is_donation_id', False),
                'amount': amount,
                'product_id': data.get('product_id'),
                # 'order_id': pos_order.id if pos_order else False,
            }
            
            payment = self.env['advance.donation.receipt'].create(payment_vals)
            _logger.info(f"Created receipt: {payment.name} with ID: {payment.id}")
            
            # Set donor from POS order partner or provided donor_id
            if pos_order and pos_order.partner_id:
                _logger.info(f"Setting donor from POS order partner: {pos_order.partner_id.id}")
                payment.write({'donor_id': pos_order.partner_id.id})
            elif data.get('donor_id'):
                _logger.info(f"Setting donor from provided donor_id: {data['donor_id']}")
                payment.write({'donor_id': data['donor_id']})
            else:
                _logger.warning("No donor information available")

            if data['payment_type'] == 'cheque':
                payment.write({
                    'bank_id': int(data['bank_id']),
                    'cheque_number': data['cheque_number'],
                    'cheque_date': data['cheque_date'],
                })
                _logger.info("Processing cheque payment...")
                payment.action_paid()
                _logger.info("Cheque payment completed")
            else:
                _logger.info("Processing cash payment...")
                payment.action_paid()
                _logger.info("Cash payment completed")

            _logger.info(f"Successfully created donation receipt: {payment.name}")
            
            return {
                "status": "success",
                "receipt_name": payment.name,
                "receipt_id": payment.id,
            }

        except Exception as e:
            _logger.error(f"Error in register_pos_payment: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "body": f"System error: {str(e)}",
            }