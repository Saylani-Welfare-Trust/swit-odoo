from odoo import models, fields, api


class DistributionCenterLine(models.Model):
    _name = 'distribution.center.line'
    _description = "Distribution Center Line"


    distribution_center_id = fields.Many2one('distribution.center', string="Distribution Center")
    product_id= fields.Many2one('product.product', string="Product")

    quantity = fields.Float('Quantity', default=1)
    
    on_hand_qty = fields.Float(
        string='On Hand',
        compute='_compute_on_hand_qty'
    )

    @api.depends('product_id')
    def _compute_on_hand_qty(self):
        for line in self:
            line.on_hand_qty = line.product_id.qty_available if line.product_id else 0.0