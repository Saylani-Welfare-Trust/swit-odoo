from odoo import fields, api, models, _
from odoo.exceptions import UserError


class MfdInstallmentReceipt(models.Model):
    _name = 'mfd.installment.receipt'

    name = fields.Char(string="Name", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    installment_id = fields.Many2one('mfd.loan.request.line', string='Installment Id')
    doc_type = fields.Selection([('sec_dep', 'Security Deposit'), ('ins_dep', 'Installment Deposit')], string='Payment Type', default='ins_dep')
    payment_type = fields.Selection([('cash', 'Cash'), ('cheque', 'Cheque')], string='Payment Method', default='cash')
    partner_id = fields.Many2one('res.partner', string='Customer', related='loan_id.customer_id')
    cnic = fields.Char(string='CNIC', related='partner_id.cnic_no')
    loan_id = fields.Many2one('mfd.loan.request', string='Loan ID')
    # loan_ids_domain = fields.Many2many('mfd.loan.request', string='Loan Id Domain')
    amount = fields.Monetary('Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='loan_id.currency_id')
    date = fields.Date(string='Date', default=fields.Date.today())
    reference = fields.Char(string='Reference')
    mfd_bank_id = fields.Many2one('mfd.bank', string='Bank Name')
    # account_number = fields.Char(string='Account Number')
    cheque_number = fields.Char(string='Cheque Number')
    cheque_date = fields.Date(string='Cheque Date')
    bounced_reason = fields.Html(string='Reason')
    is_pdc = fields.Boolean()
    status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('bounced', 'Bounced')],
        string='Status',
        default='draft')


    def action_pending(self):
        if self.doc_type == 'sec_dep':
            if self.loan_id.is_sec_dep_paid:
                raise UserError('Security Deposit is already paid for this loan')

        if self.doc_type == 'ins_dep':
            installment_ids = self.env['mfd.loan.request.line'].search([
                ('loan_request_id', '=', self.loan_id.id)
            ])
            filtered_installments = installment_ids.filtered(lambda r: r.state != 'paid')
            total_remaining_amount = sum(filtered_installments.mapped('remaining_amount'))

            if self.amount > total_remaining_amount:
                raise UserError(
                    f'You cannot pay more than the remaining amount. Remaining Amount: {total_remaining_amount}')

        if self.payment_type == 'cheque':
            credit_account = self.env.ref('microfinance_loan.cheque_deposit_credit_account_first').account_id
            debit_account = self.env.ref('microfinance_loan.cheque_deposit_debit_account_first').account_id

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

            credit_account = self.env.ref('microfinance_loan.cheque_deposit_credit_account_second').account_id
            debit_account = self.env.ref('microfinance_loan.cheque_deposit_debit_account_second').account_id

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

        self.write({'status': 'pending'})

    def action_bounced(self):
        if not self.bounced_reason:
            raise UserError('Please provide reason')
        self.write({'status': 'bounced'})

    def action_paid(self):
        # journal = self.env['account.journal'].search([('name', '=', 'MicroFinance Loan')], limit=1)
        if self.doc_type == 'sec_dep':
            if not self.loan_id.is_sec_dep_paid:
                self.loan_id.is_sec_dep_paid = True
            else:
                raise UserError('Security Deposit is already paid for this loan')

        if self.doc_type == 'ins_dep':
            installment_ids = self.env['mfd.loan.request.line'].search([
                ('loan_request_id', '=', self.loan_id.id)
            ])
            filtered_installments = installment_ids.filtered(lambda r: r.state != 'paid')
            total_remaining_amount = sum(filtered_installments.mapped('remaining_amount'))


            if self.amount > total_remaining_amount:
                raise UserError(f'You cannot pay more than the remaining amount. Remaining Amount: {total_remaining_amount}')

            sorted_installments = filtered_installments.sorted(key=lambda r: r.due_date)
            remaining_value = self.amount

            for installment in sorted_installments:
                if remaining_value <= 0:
                    break

                remaining_installment_amount = installment.amount - installment.paid_amount
                if remaining_installment_amount <= remaining_value:
                    installment.write({
                        'paid_amount': installment.amount,
                    })
                    remaining_value -= remaining_installment_amount
                else:
                    installment.write({
                        'paid_amount': installment.paid_amount + remaining_value
                    })
                    remaining_value = 0


            if self.loan_id.recovery_id:
                remaining_value = self.amount
                recovery_installments = self.loan_id.recovery_id.recovery_request_lines
                filtered_installments = recovery_installments.filtered(lambda r: r.state != 'paid')
                sorted_installments = filtered_installments.sorted(key=lambda r: r.due_date)

                print(sorted_installments, 'sorted_installments')

                for installment in sorted_installments:
                    if remaining_value <= 0:
                        break

                    remaining_installment_amount = installment.amount - installment.paid_amount
                    if remaining_installment_amount <= remaining_value:
                        installment.write({
                            'paid_amount': installment.amount,
                        })
                        remaining_value -= remaining_installment_amount
                    else:
                        installment.write({
                            'paid_amount': installment.paid_amount + remaining_value
                        })
                        remaining_value = 0


        if self.payment_type == 'cash':
            credit_account = self.env.ref('microfinance_loan.cash_payment_credit_account').account_id
            debit_account = self.env.ref('microfinance_loan.cash_payment_debit_account').account_id

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
            credit_account = self.env.ref('microfinance_loan.cheque_payment_credit_account_first').account_id
            debit_account = self.env.ref('microfinance_loan.cheque_payment_debit_account_first').account_id

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

            credit_account = self.env.ref('microfinance_loan.cheque_payment_credit_account_second').account_id
            debit_account = self.env.ref('microfinance_loan.cheque_payment_debit_account_second').account_id

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



        # for rec in self:
        #     installment = self.env['mfd.loan.request.line'].search([
        #         ('installment_id', '=', rec.reference)
        #     ], limit=1)
        #     if installment:
        #         installment.state = 'paid'
        if self.doc_type == 'ins_dep':
            self.loan_id.installment_paid_amount += self.amount
            if self.loan_id.installment_paid_amount >= self.loan_id.total_amount:
                self.loan_id.write({'state': 'paid'})
        self.write({'status': 'paid'})


    def action_redeposit_cheque(self):
        action = self.env.ref('microfinance_loan.action_mfd_installment_receipt').read()[0]
        form_view_id = self.env.ref('microfinance_loan.view_mfd_installment_receipt_form').id
        action['views'] = [
            [form_view_id, 'form']
        ]
        action['context'] = {
            'default_loan_id': self.loan_id.id,
            'default_partner_id': self.partner_id.id,
            'default_amount': self.amount,
            # 'default_is_mfd_loan': True,
            'default_payment_type': self.payment_type,
            'default_currency_id': self.currency_id.id,
            'default_installment_id': self.installment_id.id,
            'default_mfd_bank_id': self.mfd_bank_id.id,
            'default_cheque_number': self.cheque_number,
            'default_cheque_date': self.cheque_date
        }
        return action

    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            doc_type = vals.get('doc_type')
            if doc_type == 'sec_dep':
                vals['name'] = self.env['ir.sequence'].next_by_code('mfd.sec_dep.receipt') or ('New')
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('mfd.installment.receipt') or ('New')
        return super().create(vals)

    @api.onchange('loan_id', 'doc_type')
    def compute_amount(self):
        if self.doc_type == 'sec_dep':
            if self.loan_id:
                if self.loan_id.asset_type != 'cash':
                    self.amount = self.loan_id.security_deposit

    def print_receipt(self):
        return self.env.ref('microfinance_loan.report_mfd_installment_receipt').report_action(self)

    # @api.onchange('partner_id')
    # def compute_loan_domain(self):
    #     self.loan_id = False
    #     if self.partner_id:
    #         self.loan_ids_domain = self.env['mfd.loan.request'].search([
    #             ('customer_id', '=', self.partner_id.id),
    #             ('state', '=', 'done')
    #         ])
    #     else:
    #         self.loan_ids_domain = False

    # @api.onchange('loan_id')
    # def compute_currency_id(self):
    #     for rec in self:
    #         if rec.loan_id:
    #             rec.partner_id = rec.loan_id.customer_id.id
    #             rec.currency_id = rec.loan_id.currency_id.id
    #         else:
    #             rec.partner_id = False
    #             rec.currency_id = False


