from odoo import fields, api, models,_

class MfdLoanRequestLine(models.Model):
    _name = 'mfd.loan.request.line'
    _description = 'Microfinance Loan Request Installment'

    loan_request_id = fields.Many2one('mfd.loan.request', string='Loan Id', required=True, ondelete='cascade')
    loan_state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'HOD Approval'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('rejected', 'Rejected')], related='loan_request_id.state')
    installment_number = fields.Integer('Installment Number', required=True)
    installment_id = fields.Char('Installment Id', required=True)
    due_date = fields.Date('Due Date', required=True)
    amount = fields.Monetary('Amount', currency_field='currency_id')
    paid_amount = fields.Monetary('Paid Amount', currency_field='currency_id')
    remaining_amount = fields.Monetary('Remaining Amount', currency_field='currency_id', compute='_compute_remaining_amount')
    currency_id = fields.Many2one('res.currency', 'Currency', related='loan_request_id.currency_id', readonly=True)
    is_cheque_deposit = fields.Boolean()
    state = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid')],
        string='Status', compute='_compute_installment_state', help=" * Unpaid: The installment is not paid yet.\n * Paid: The installment is paid.\n * Overdue: The installment is overdue.")
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


    # def create_pir(self):
    #     action = self.env.ref('microfinance_loan.action_mfd_installment_receipt').read()[0]
    #     form_view_id = self.env.ref('microfinance_loan.view_mfd_installment_receipt_form').id
    #     action['views'] = [
    #         [form_view_id, 'form']
    #     ]
    #     action['context'] = {
    #             'default_partner_id':  self.loan_request_id.customer_id.id,
    #             'default_amount': self.amount,
    #             # 'default_is_mfd_loan': True,
    #             'default_reference': self.installment_id,
    #             'default_installment_id': self.id,
    #             'default_currency_id': self.currency_id.id,
    #             'default_mfd_bank_id': self.mfd_bank_id.id,
    #             'default_cheque_date': self.cheque_date,
    #             'default_cheque_number': self.cheque_no
    #     }
    #     return action
    #
    #     view_id = self.env.ref('microfinance_loan.mfd_pir_receipt_form').id
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Installment Receipt',
    #         'res_model': 'account.payment',
    #         'view_mode': 'form',
    #         'view_type': 'form',
    #         'view_id': view_id,
    #         'context': {
    #             'default_partner_id':  self.loan_request_id.customer_id.id,
    #             'default_amount': self.amount,
    #             'default_is_mfd_loan': True,
    #             'default_ref': self.installment_id
    #         },
    #         'target': 'current',
    #     }

    # def go_to_pir(self):
    #     action = self.env.ref('microfinance_loan.action_mfd_installment_receipt').read()[0]
    #     tree_view_id = self.env.ref('microfinance_loan.view_mfd_installment_receipt_tree').id
    #     form_view_id = self.env.ref('microfinance_loan.view_mfd_installment_receipt_form').id
    #     action['views'] = [
    #         [tree_view_id, 'tree'],
    #         [form_view_id, 'form']
    #     ]
    #     action['domain'] = [('reference', '=', self.installment_id)]
    #     return action


    # def _compute_check_payment_id(self):
    #     for rec in self:
    #         installment_receipt = self.env['mfd.installment.receipt'].search([
    #             ('reference', '=' , rec.installment_id)
    #         ], limit=1)
    #         if installment_receipt:
    #             rec.is_payment_done = True
    #             rec.payment_id = installment_receipt.id
    #         else:
    #             rec.is_payment_done = False


    def deposit_cheque(self):
        for rec in self:
            if not rec.is_cheque_deposit:
                rec.is_cheque_deposit = True
                payment = self.env['mfd.installment.receipt'].create({
                    'payment_type': 'cheque',
                    'loan_id': rec.loan_request_id.id,
                    'amount': rec.cheque_amount,
                    'currency_id': rec.currency_id.id,
                    'mfd_bank_id': rec.mfd_bank_id.id,
                    'cheque_number': rec.cheque_no,
                    'cheque_date': rec.cheque_date,
                    'is_pdc': True
                })
                payment.action_pending()