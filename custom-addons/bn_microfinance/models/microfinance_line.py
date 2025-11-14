from odoo import models, fields, api, _


state_selection = [
    ('unpaid', 'Unpaid'),
    ('partial', 'Partial'),
    ('paid', 'Paid')
]


class MicrofinanceLine(models.Model):
    _name = 'microfinance.line'
    _description = "Microfinance Line"


    microfinance_id = fields.Many2one('microfinance', string="Microfinance")
    
    bank_name = fields.Char('Bank Name')
    cheque_no = fields.Char('Cheque No.')
    name = fields.Char('Name', default="NEW")
    installment_no = fields.Char('Installment No.')

    due_date = fields.Date('Due Date')
    cheque_date = fields.Date('Cheque Date')
    
    amount = fields.Monetary('Amount', currency_field='currency_id', default=0)
    paid_amount = fields.Monetary('Paid Amount', currency_field='currency_id', default=0)
    remaining_amount = fields.Monetary('Remaining Amount', currency_field='currency_id', compute='_compute_remaining_amount', store=True)

    currency_id = fields.Many2one(related='microfinance_id.currency_id', string="Currency")

    state = fields.Selection(selection=state_selection, string='State')

    is_cheque_deposit = fields.Boolean('Is Cheque Deposit')


    @api.model
    def create(self, vals):
        if vals.get('name', _('NEW') == _('NEW')):
            vals['name'] = self.env['ir.sequence'].next_by_code('microfinance_line') or ('New')
                
        return super(MicrofinanceLine, self).create(vals)
    
    @api.depends('due_date')
    def _compute_remaining_amount(self):
        for rec in self:
            rec.remaining_amount = rec.amount - rec.paid_amount

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