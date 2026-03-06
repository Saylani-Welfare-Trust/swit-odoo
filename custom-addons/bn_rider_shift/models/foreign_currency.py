from odoo import models, fields


state_selection = [
    ('draft', 'Draft'),
    ('converted', 'Converted'),
    ('reject', 'Reject'),
]


class ForeignCurrency(models.Model):
    _name = 'foreign.currency'
    _description = "Foreign Currency"


    currency_id = fields.Many2one('res.currency', string="Currency")
    
    amount = fields.Float('Amount')

    conversion_rate = fields.Float('Conversion Rate', default=1.0)

    rider_id = fields.Many2one('hr.employee', string="Rider")
    lot_id = fields.Many2one('stock.lot', string="Lot")

    state = fields.Selection(selection=state_selection, string="State", default='draft')


    def action_convert_amount(self):
        self.amount = self.curruncy_id._convert(self.amount, self.env.company.currency_id, self.env.company, fields.Date.today())
        self.state = 'converted'

    def action_reject(self):
        self.state = 'reject'