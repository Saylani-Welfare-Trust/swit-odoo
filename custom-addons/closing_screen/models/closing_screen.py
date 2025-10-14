from odoo import models, fields, api


class ClosingScreen(models.Model):
    _name = 'closing.screen'

    name = fields.Char(string='Name')

    name = fields.Char(string='Name')
    pos_session = fields.Many2one('pos.session',string="Session")

    line_id = fields.One2many('closing.screen.line','master_id',string='line')
    state = fields.Selection([('draft','Draft'),('confirm','Confirmed')],string='State')


    def action_confirm(self):
        self.state = 'confirm'

class CloseLine(models.Model):
    _name = 'closing.screen.line'

    master_id = fields.Many2one('closing.screen',string='Master')
    payment_method = fields.Many2one('pos.payment.method')
    amount = fields.Float(string='Amount')
    deposit_slip = fields.Integer(string='Deposite Slip Number')
    pos_category = fields.Many2one('pos.category',string='Category')



