from odoo import models, fields


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    sadqa_jariya_line_id = fields.Many2one('sadqa.jariya.line', string='Sadqa e Jariya Line')
    sadqa_jariya_recurring_line_id = fields.Many2one('sadqa.jariya.recurring.line', string='Sadqa e Jariya Recurring Line')

    def button_validate(self):
        """A validated delivery disburses its line (sudo: the warehouse user
        needs no Sadqa e Jariya access)"""
        res = super().button_validate()
        for picking in self.sudo().filtered(lambda p: p.state == 'done'):
            line = picking.sadqa_jariya_recurring_line_id or picking.sadqa_jariya_line_id
            if line.state == 'delivered':
                line.action_disbursed()
        return res
