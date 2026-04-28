from odoo import models, fields, api, _


state_selection = [
    ('draft', 'Draft'),
    ('posted', 'Posted')
]


class Donation(models.Model):
    _name = 'donation'
    _description = "Donation"


    donor_id = fields.Many2one('res.partner', string="Donor / Student")
    journal_id = fields.Many2one('account.journal', string="Journal")
    product_id = fields.Many2one('product.product', string="Product")
    gateway_config_id = fields.Many2one('gateway.config', string="Gateway Config")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.user.company_id.id)
    currency_id = fields.Many2one(related='company_id.currency_id', string="Currency")

    name = fields.Char('Name', default="New")
    transaction_id = fields.Char('Transaction ID')

    reference = fields.Text('Reference/Remarks')
    
    date = fields.Char('Date')

    amount = fields.Monetary('Amount')

    is_fee = fields.Boolean('Is Fee')

    state = fields.Selection(selection=state_selection, string="State", default="draft")


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('import_donation') or ('New')

        return super(Donation, self).create(vals)
    
    def action_confirm(self):
        self.state = 'posted'
    
    def action_draft(self):
        self.state = 'draft'