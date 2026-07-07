from odoo import models, fields, api, _


state_selection = [
    ('unpaid', 'Unpaid'),
    ('partial', 'Partial'),
    ('paid', 'Paid')
]
state_cheque_selection = [
    ('draft', 'Draft'),
    ('deposited', 'Deposited'),
    ('cleared', 'Cleared'),
    ('bounced', 'Bounced')
]

class MicrofinanceLine(models.Model):
    _name = 'microfinance.line'
    _description = "Microfinance Line"


    microfinance_id = fields.Many2one('microfinance', string="Microfinance")
    
    bank_name = fields.Char('Bank Name')
    cheque_no = fields.Char('Cheque No.')
    name = fields.Char('Name', default="NEW")
    installment_no = fields.Char('Installment No.')
    installment_number = fields.Char('Installment Number')
    amount_total = fields.Monetary('Amount Total', currency_field='currency_id')

    due_date = fields.Date('Due Date')
    cheque_date = fields.Date('Cheque Date')
    payment_type = fields.Selection(selection=[
        ('security', 'Security Deposit'),
        ('installment', 'Installment Payment')
    ], string="Payment Type")
    
    amount = fields.Monetary('Amount', currency_field='currency_id', default=0)
    paid_amount = fields.Monetary('Paid Amount', currency_field='currency_id', default=0)
    remaining_amount = fields.Monetary('Remaining Amount', currency_field='currency_id', compute='_compute_remaining_amount', store=True)
    donee_id = fields.Many2one('res.partner', string="Donee")
    currency_id = fields.Many2one(related='microfinance_id.currency_id', string="Currency")

    state = fields.Selection(selection=state_selection, string='State', default="unpaid")
    state_cheque = fields.Selection(selection=state_cheque_selection, string='Cheque Status', default='draft')
    is_cheque_deposit = fields.Boolean('Is Cheque Deposit')
    payment_id = fields.Many2one('microfinance.installment', string="Payment Reference")
    payment_date = fields.Date('Payment Date')

    currency_id = fields.Many2one('res.currency', related='microfinance_id.currency_id', store=True)
    @api.depends('state')
    def _get_payment_status(self):
        for line in self:
            if line.state == 'paid':
                line.payment_status = 'Fully Paid'
            elif line.state == 'partial':
                line.payment_status = 'Partially Paid'
            else:
                line.payment_status = 'Unpaid'
    
    payment_status = fields.Char(compute='_get_payment_status', string='Payment Status')

    @api.model
    def create(self, vals):
        if vals.get('name', _('NEW') == _('NEW')):
            vals['name'] = self.env['ir.sequence'].next_by_code('microfinance_line') or ('New')
                
        return super(MicrofinanceLine, self).create(vals)
    
    @api.depends('due_date', 'paid_amount')
    def _compute_remaining_amount(self):
        for rec in self:
            rec.remaining_amount = rec.amount - rec.paid_amount

    def _apply_direct_deposit_payment(self, amount, payment_date=None):
        self.ensure_one()
        if amount <= 0:
            return 0

        outstanding_amount = max(self.amount - self.paid_amount, 0)
        if outstanding_amount <= 0:
            return 0

        applied_amount = min(outstanding_amount, amount)
        new_paid_amount = self.paid_amount + applied_amount
        new_state = 'paid' if new_paid_amount >= self.amount else 'partial'

        self.write({
            'paid_amount': new_paid_amount,
            'payment_date': payment_date or fields.Date.today(),
            'state': new_state,
        })

        return applied_amount

    def action_cheque_deposit(self):
        if not self.is_cheque_deposit:
            self.is_cheque_deposit = True

            # microfinance_installment = self.env['microfinance.installment'].create({
            self.env['microfinance.installment'].create({
                'payment_type': 'installment',
                'payment_method': 'cheque',
                'microfinance_id': self.microfinance_id.id,
                'amount': self.amount,
                'currency_id': self.currency_id.id,
                'bank_name': self.bank_name,
                'cheque_no': self.cheque_no,
                'cheque_date': self.cheque_date,
                'donee_id': self.microfinance_id.donee_id.id,
            })

    def write(self, vals):
        res = super().write(vals)
        
        if 'state' in vals or 'paid_amount' in vals:
            for rec in self:
                # Only sync state_cheque if this line has a cheque deposit
                # If no cheque exists, state goes to paid normally — nothing extra happens
                if not rec.is_cheque_deposit:
                    continue  # ← skip, only installment state updates, state_cheque untouched
                
                if rec.state == 'paid':
                    if rec.state_cheque not in ('cleared', 'bounced'):
                        rec.state_cheque = 'deposited'
                elif rec.state in ('unpaid', 'partial'):
                    if rec.state_cheque == 'deposited':
                        rec.state_cheque = 'draft'
        
        return res

    @api.depends('state', 'paid_amount')
    def _sync_cheque_state(self):
        for rec in self:
            # Only sync if this line was created via cheque deposit
            if not rec.is_cheque_deposit:
                continue
            
            if rec.state == 'paid':
                rec.state_cheque = 'deposited'
            elif rec.state == 'partial':
                rec.state_cheque = 'deposited'  # partially deposited, still counts as deposited
            elif rec.state == 'unpaid':
                rec.state_cheque = 'draft'      # reset if payment reversed