from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    sadqa_jariya_line_id = fields.Many2one('sadqa.jariya.line', string='Sadqa e Jariya Line')
    sadqa_jariya_recurring_line_id = fields.Many2one('sadqa.jariya.recurring.line', string='Sadqa e Jariya Recurring Line')
