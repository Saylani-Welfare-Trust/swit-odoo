from odoo import models, api, fields
from odoo.exceptions import UserError as Warning

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    recurring_line_id = fields.Many2one('welfare.recurring.line', string='Welfare Recurring Line', store=True)
    welfare_line_id = fields.Many2one('welfare.line', string='Welfare Line', store=True)

    def button_validate(self):
        """Override to auto-complete/disburse welfare and recurring lines when picking is validated"""
        res = super().button_validate()
        Welfare = self.env['welfare']
        for picking in self:
            if picking.origin:
                welfare = Welfare.search([('name', '=', picking.origin)], limit=1)
                if welfare:
                    # Only disburse recurring line linked to this picking
                    if picking.recurring_line_id and picking.recurring_line_id.state == 'delivered':
                        # raise Warning(f"Recurring line: {picking.recurring_line_id}\nWelfare name: {welfare.name}")
                        picking.recurring_line_id.action_disbursed()
                    # CASE 2: No recurring line → use welfare_line_id
                    elif picking.welfare_line_id and picking.welfare_line_id.state == 'delivered':
                        # raise Warning(f"Welfare line: {picking.welfare_line_id}\nWelfare name: {welfare.name}")
                        picking.welfare_line_id.action_disbursed()
        return res