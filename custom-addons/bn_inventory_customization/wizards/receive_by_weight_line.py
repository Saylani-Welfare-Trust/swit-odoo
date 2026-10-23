from odoo import models, fields, api


class ReceiveByWeightLine(models.TransientModel):
    _name = 'receive.by.weight.line'
    _description = "Receive By Weight Line"

    s_no = fields.Integer(string="S.No", store=True)
    
    wizard_id = fields.Many2one('receive.by.weight')
    product_id = fields.Many2one('product.product', required=True)
    quantity = fields.Float(string="Quantity")
    
    livestock_variant = fields.Many2one(
        comodel_name='livestock.variant',
        string='Livestock Variant',
        default=lambda self: self.env['livestock.variant'].search([('name', 'ilike', 'sadqa')], limit=1),
        required=False
    )

    weight = fields.Float(string="Weight (kg)")

    available_product_ids = fields.Many2many('product.product', compute='_compute_available_products')
    allowed_product_ids = fields.Many2many('product.product', compute='_compute_allowed_product_ids')

    @api.depends('wizard_id.picking_id')
    def _compute_allowed_product_ids(self):
        for line in self:
            picking = line.wizard_id.picking_id
            if picking:
                product_ids = picking.move_ids.mapped('product_id').ids
                line.allowed_product_ids = [(6, 0, product_ids)]
            else:
                line.allowed_product_ids = [(6, 0, [])]
    
    @api.depends('wizard_id.picking_id')
    def _compute_available_products(self):
        """Compute available products based on the picking."""
        for line in self:
            picking = line.wizard_id.picking_id
            if picking:
                product_ids = picking.move_ids.mapped('product_id').ids
                line.available_product_ids = [(6, 0, product_ids)]
            else:
                line.available_product_ids = [(6, 0, [])]