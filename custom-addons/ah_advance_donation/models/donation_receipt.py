from odoo import fields,api,models,_
from odoo.exceptions import UserError


class DonationReceipt(models.Model):
    _name = 'ah.advance.donation.receipt'

    name = fields.Char(string="Name", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    payment_type = fields.Selection([('cash', 'Cash'), ('cheque', 'Cheque')], string='Payment Method', default='cash')
    is_donation_id = fields.Boolean('Donation ID?')
    donation_id = fields.Many2one('ah.advance.donation', string='Donation ID')
    partner_id = fields.Many2one('adv.don.customer', string='Customer')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)
    amount = fields.Monetary('Amount', currency_field='currency_id')
    used_amount = fields.Monetary('Used Amount', currency_field='currency_id', default=0, compute='_compute_amount', store=True)
    remaining_amount = fields.Monetary('Remaining Amount', currency_field='currency_id', compute='_compute_amount', store=True)
    update_used_amount = fields.Boolean('Update')
    date = fields.Date(string='Date', default=fields.Date.today())

    bank_id = fields.Many2one('config.bank', 'Bank Name')
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



    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('ah.advance.donation.receipt') or ('New')
        return super().create(vals)

    @api.onchange('donation_id')
    def onchange_donation_id(self):
        if self.donation_id:
            self.partner_id = self.donation_id.customer_id.id

    @api.onchange('is_donation_id')
    def onchange_is_donation_id(self):
        self.donation_id = False


    def action_pending(self):
        if self.payment_type == 'cheque':
            credit_account = self.env.ref('ah_advance_donation.cheque_deposit_credit_account_first').account_id
            debit_account = self.env.ref('ah_advance_donation.cheque_deposit_debit_account_first').account_id

            move_lines = [
                {
                    'name': f'{self.name}',
                    'account_id': credit_account.id,
                    'credit': self.amount,
                    'debit': 0.0,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                },
                {
                    'name': f'{self.name}',
                    'account_id': debit_account.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                }
            ]
            move = self.env['account.move'].create({
                'ref': f'{self.name}',
                'partner_id': self.partner_id.id,
                # 'journal_id': journal.id,
                'line_ids': [(0, 0, line) for line in move_lines],
                'date': fields.Date.today(),
                'move_type': 'entry',
            })
            move.action_post()

            credit_account = self.env.ref('ah_advance_donation.cheque_deposit_credit_account_second').account_id
            debit_account = self.env.ref('ah_advance_donation.cheque_deposit_debit_account_second').account_id

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
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                },
                {
                    'name': f'{self.name}',
                    'account_id': debit_account.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                }
            ]
            move = self.env['account.move'].create({
                'ref': f'{self.name}',
                'partner_id': self.partner_id.id,
                # 'journal_id': journal.id,
                'line_ids': [(0, 0, line) for line in move_lines],
                'date': fields.Date.today(),
                'move_type': 'entry',
            })
            move.action_post()

        self.write({'state': 'pending'})


    def action_bounced(self):
        if not self.bounced_reason:
            raise UserError('Please provide reason')
        self.write({'state': 'bounced'})


    def action_paid(self):
        if self.donation_id:
            donation_lines = self.donation_id.advance_donation_lines
            unpaid_donation_lines = donation_lines.filtered(lambda r: r.state != 'paid')
            total_remaining_amount = sum(unpaid_donation_lines.mapped('remaining_amount'))

            if self.amount > total_remaining_amount:
                raise UserError(
                    f'You cannot pay more than the remaining amount. Remaining Amount: {total_remaining_amount}')
            self.donation_id.donation_slip_ids = [(4, self.id)]
        #
        # remaining_value = self.amount
        #
        # for unpaid_donation_line in unpaid_donation_lines:
        #     if remaining_value <= 0:
        #         break
        #
        #     remaining_installment_amount = unpaid_donation_line.amount - unpaid_donation_line.paid_amount
        #     if remaining_installment_amount <= remaining_value:
        #         unpaid_donation_line.write({
        #             'paid_amount': unpaid_donation_line.amount,
        #         })
        #         remaining_value -= remaining_installment_amount
        #     else:
        #         unpaid_donation_line.write({
        #             'paid_amount': unpaid_donation_line.paid_amount + remaining_value
        #         })
        #         remaining_value = 0

        if self.payment_type == 'cash':
            credit_account = self.env.ref('ah_advance_donation.cash_payment_credit_account').account_id
            debit_account = self.env.ref('ah_advance_donation.cash_payment_debit_account').account_id

            if not credit_account:
                raise UserError('No Credit Account found')
            if not debit_account:
                raise UserError('No Debit Account found')
        # if not journal:
        #     raise UserError('No Journal found')

            move_lines = [
                {
                    'name': f'{self.name}',
                    'account_id': credit_account.id,
                    'credit': self.amount,
                    'debit': 0.0,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                },
                {
                    'name': f'{self.name}',
                    'account_id': debit_account.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                }
            ]
            move = self.env['account.move'].create({
                'ref': f'{self.name}',
                'partner_id': self.partner_id.id,
                # 'journal_id': journal.id,
                'line_ids': [(0, 0, line) for line in move_lines],
                'date': fields.Date.today(),
                'move_type': 'entry',
            })

            move.action_post()

        if self.payment_type == 'cheque':
            credit_account = self.env.ref('ah_advance_donation.cheque_payment_credit_account_first').account_id
            debit_account = self.env.ref('ah_advance_donation.cheque_payment_debit_account_first').account_id

            move_lines = [
                {
                    'name': f'{self.name}',
                    'account_id': credit_account.id,
                    'credit': self.amount,
                    'debit': 0.0,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                },
                {
                    'name': f'{self.name}',
                    'account_id': debit_account.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                }
            ]
            move = self.env['account.move'].create({
                'ref': f'{self.name}',
                'partner_id': self.partner_id.id,
                # 'journal_id': journal.id,
                'line_ids': [(0, 0, line) for line in move_lines],
                'date': fields.Date.today(),
                'move_type': 'entry',
            })
            move.action_post()

            credit_account = self.env.ref('ah_advance_donation.cheque_payment_credit_account_second').account_id
            debit_account = self.env.ref('ah_advance_donation.cheque_payment_debit_account_second').account_id

            move_lines = [
                {
                    'name': f'{self.name}',
                    'account_id': credit_account.id,
                    'credit': self.amount,
                    'debit': 0.0,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                },
                {
                    'name': f'{self.name}',
                    'account_id': debit_account.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id if self.currency_id else None,
                }
            ]
            move = self.env['account.move'].create({
                'ref': f'{self.name}',
                'partner_id': self.partner_id.id,
                # 'journal_id': journal.id,
                'line_ids': [(0, 0, line) for line in move_lines],
                'date': fields.Date.today(),
                'move_type': 'entry',
            })
            move.action_post()

        self.write({'state': 'paid'})


    def action_redeposit_cheque(self):
        action = self.env.ref('ah_advance_donation.action_advance_donation_receipt').read()[0]
        form_view_id = self.env.ref('ah_advance_donation.view_advance_donation_receipt_form').id
        action['views'] = [
            [form_view_id, 'form']
        ]
        action['context'] = {
            'default_loan_id': self.donation_id.id,
            'default_partner_id': self.partner_id.id,
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
        if data['is_donation_id'] == True:
            if not data['donation_id']:
                return {
                    "status": "error",
                    "body": "Please enter Donation ID",
                }
            donation_id = self.env['ah.advance.donation'].sudo().search([('name', '=', data['donation_id'])], limit=1)
            if not donation_id:
                return {
                    "status": "error",
                    "body": "Record not found",
                }

        if not data['amount'] or float(data['amount']) <= 0:
            return {
                "status": "error",
                "body": "Please enter amount",
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
        payment = self.env['ah.advance.donation.receipt'].create({
            'payment_type': data['payment_type'],
            'is_donation_id': data['is_donation_id'],
            'amount': data['amount'],
        })
        if data['is_donation_id'] == True:
            payment.write({'donation_id': donation_id})
            payment.onchange_donation_id()
        else:
            payment.write({'partner_id': data['partner_id']})

        if data['payment_type'] == 'cheque':
            payment.write({
                'bank_id': int(data['bank_id']),
                'cheque_number': data['cheque_number'],
                'cheque_date': data['cheque_date'],
            })
            payment.action_pending()
        else:
            payment.action_paid()

        return {
            "status": "success",
        }





