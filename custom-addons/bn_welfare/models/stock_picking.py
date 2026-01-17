from odoo import models, api, fields
from odoo.exceptions import UserError as Warning

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'
    recurring_line_id = fields.Many2one('welfare.recurring.line', string='Welfare Recurring Line')

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        """Override to auto-complete/disburse welfare and recurring lines when picking is validated"""
        res = super().button_validate()
        Welfare = self.env['welfare']
        for picking in self:
            if picking.origin:
                welfare = Welfare.search([('name', '=', picking.origin)], limit=1)
                if welfare:
                    # Only disburse recurring lines linked to this picking
                    recurring_lines = picking.move_line_ids.mapped('recurring_line_id').filtered(lambda l: l and l.state != 'disbursed')
                    for line in recurring_lines:
                        line.state = 'disbursed'
                    # If all recurring lines are disbursed, disburse the welfare
                    if welfare.welfare_recurring_line_ids and all(l.state == 'disbursed' for l in welfare.welfare_recurring_line_ids):
                        welfare.state = 'disbursed'
                    if not welfare.welfare_recurring_line_ids:
                        # raise Warning(welfare.welfare_recurring_line_ids)
                        welfare.state = 'disbursed'
        return res