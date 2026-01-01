from odoo import models, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        """Override to auto-complete microfinance record when picking is validated"""
        res = super().button_validate()
        
        # Check if this picking is linked to a microfinance record
        for picking in self:
            if picking.origin and picking.state == 'done':
                # Search for microfinance record with this origin
                microfinance = self.env['microfinance'].search([
                    ('name', '=', picking.origin),
                    # ('state', '=', 'wfd')
                ], limit=1)
                
                if microfinance:
                    # Complete the microfinance record
                    microfinance._complete_after_picking()
        
        return res
