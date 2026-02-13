from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    recurring_line_id = fields.Many2one('welfare.recurring.line', string='Welfare Recurring Line', store=True)
    welfare_line_id = fields.Many2one('welfare.line', string='Welfare Line', store=True)
