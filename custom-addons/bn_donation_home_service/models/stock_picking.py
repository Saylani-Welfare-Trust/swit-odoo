from odoo import models, fields, _
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'


    dhs_id = fields.Many2one('donation.home.service', 'Donation Home Service')
    

    def _create_live_stock_slaughter_cutting(self):
        """Create live_stock_slaughter.cutting record based on the picking"""
        for move in self.move_ids:
            product = move.product_id
            # raise UserError(str(move.product_id.read()))
            if product and product.detailed_type == 'product':
                # Get the product template
                product_template = product.product_tmpl_id

                # Create live stock slaughter cutting record
                cutting_vals = {
                    'product': product_template.id,
                    'quantity': move.quantity,
                    'price': product.lst_price or 0.0,  # Using list price
                    'product_code': product.default_code ,
                    'origin': self.origin if self.origin else self.origin.replace('Gate In against ', ''),
                    
                }
                
                self.env['live_stock_slaughter.live_stock_slaughter'].create(cutting_vals)