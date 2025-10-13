from odoo import fields, models, api, exceptions, _


state_selection = [
    ('draft', 'Draft'),
    ('posted', 'Posted')
]


class Donation(models.Model):
    _name = 'donation'
    _description = 'Donation'


    name = fields.Char('Name')
    file_ref = fields.Char('File Reference')
    transaction_id = fields.Char('Transaction ID')

    reference = fields.Text('Reference/Remarks')
    
    partner_id = fields.Many2one('res.partner', string="Donor Name")
    journal_id = fields.Many2one('account.journal', string="Journal")
    product_id = fields.Many2one('product.product', string="Product Name")
    payment_method_id = fields.Many2one('config.bank', string="Payment Method")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account ID")
    company_id = fields.Many2one('res.company', store=True, copy=False, string="Company", default=lambda self: self.env.user.company_id.id)
    currency_id = fields.Many2one('res.currency', string="Currency", related='company_id.currency_id', default=lambda self: self.env.user.company_id.currency_id.id)

    gateway_id = fields.Many2one('config.bank', string="Bank ID")
    credit_account_id = fields.Many2one('account.account', string="Account ID")

    date = fields.Char('Donation Date')

    amount = fields.Monetary('Amount')

    state = fields.Selection(selection=state_selection, string="State", default="draft")


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('donation') or ('New')

        return super().create(vals)
    
    def action_confirm(self):
        self.state = 'posted'
    
    def action_draft(self):
        self.state = 'draft'