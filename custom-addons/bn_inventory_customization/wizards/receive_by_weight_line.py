from odoo import models, fields, api


class ReceiveByWeightLine(models.TransientModel):
    _name = 'receive.by.weight.line'
    _description = "Receive By Weight Line"

    s_no = fields.Integer(string="S.No", store=True)
    product_id = fields.Many2one('product.product', string="Product")
    livestock_product_id = fields.Many2one('product.product', string='Livestock Product')
    receive_by_weight_id = fields.Many2one('receive.by.weight', string="Receive By Weight")
    
    quantity = fields.Float(string="Quantity")

    weight = fields.Float('Weight (kg)')

    allowed_product_ids = fields.Many2many('product.product', compute='_compute_allowed_product_ids')


    @api.depends('receive_by_weight_id.picking_id')
    def _compute_allowed_product_ids(self):
        for line in self:
            picking = line.receive_by_weight_id.picking_id
            
            if picking:
                product_ids = picking.move_ids.mapped('product_id').ids
                line.allowed_product_ids = [(6, 0, product_ids)]
            else:
                line.allowed_product_ids = [(6, 0, [])]