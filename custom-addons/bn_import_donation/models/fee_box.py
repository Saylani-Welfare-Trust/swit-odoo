from odoo import fields, models, api, exceptions, _


state_selection = [
    ('draft', 'Draft'),
    ('posted', 'Posted')
]


class FeeBox(models.Model):
    _name = 'fee.box'
    _description = 'Fee Box'


    name = fields.Char('Name')
    file_ref = fields.Char('File Reference')
    transaction_id = fields.Char('Transaction ID')
    
    partner_id = fields.Many2one('res.partner', string="Donor Name")
    journal_id = fields.Many2one('account.journal', string="Journal")
    course_id = fields.Many2one('product.product', string="Course Name")
    payment_method_id = fields.Many2one('config.bank', string="Payment Method")
    company_id = fields.Many2one('res.company', store=True, copy=False, string="Company", default=lambda self: self.env.user.company_id.id)
    currency_id = fields.Many2one('res.currency', string="Currency", related='company_id.currency_id', default=lambda self: self.env.user.company_id.currency_id.id)

    gateway_id = fields.Many2one('config.bank', string="Bank ID")

    date = fields.Char('Donation Date')

    amount = fields.Monetary('Amount')

    state = fields.Selection(selection=state_selection, string="State", default="draft")


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('fee_box') or ('New')

        return super().create(vals)
    
    def action_confirm(self):
        for_credit = None
        for_debit = None

        flag = False

        if self.course_id.product_entry_line:
            for line in self.course_id.product_entry_line:
                if line.online_payment_method_id.name == 'Bank':
                    for_credit = line.for_credit
                    for_debit = line.for_debit

                    flag = False
                    break
                else:
                    flag = True
        else:
            raise exceptions.ValidationError('Please Configure Accounts on Course Product')
            
        if flag:
            raise exceptions.ValidationError('Please Configure Accounts with Payment Method Bank in Course Product')
        
        self.state = 'posted'
    
    def action_draft(self):
        self.state = 'draft'