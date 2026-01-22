from odoo import models, api, fields
from odoo.exceptions import UserError as Warning

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'
    recurring_line_id = fields.Many2one('welfare.recurring.line', string='Welfare Recurring Line')
    welfare_line_id = fields.Many2one('welfare.line', string='Welfare Line')
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
                    if welfare.welfare_recurring_line_ids:
                        recurring_lines = picking.move_line_ids.mapped('recurring_line_id').filtered(lambda l: l and l.state != 'disbursed')
                        # raise Warning(f"Recurring lines: {recurring_lines}\nWelfare name: {welfare.name}")
                        for line in recurring_lines:
                            line.state = 'disbursed'                
                    # -------------------------------------------------
                    # CASE 2: No recurring lines → use welfare_line_id
                    # -------------------------------------------------
                    elif welfare.welfare_line_ids:
                        welfare_lines = (
                            picking.move_line_ids.mapped('welfare_line_id').filtered(lambda l: l and l.state != 'disbursed'))
                        for line in welfare_lines:
                            line.state = 'disbursed'
        return res