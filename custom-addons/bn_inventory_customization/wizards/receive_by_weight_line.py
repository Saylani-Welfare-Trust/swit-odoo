from odoo import api, fields, models


class ReceiveByWeightLine(models.TransientModel):
    """Units of a livestock product of one weight: received as the product
    variant of the weight band that weight falls in."""
    _name = 'receive.by.weight.line'
    _description = "Receive By Weight Line"
    _order = 's_no, id'

    s_no = fields.Integer(string="S.No")
    wizard_id = fields.Many2one('receive.by.weight', required=True, ondelete='cascade')
    # the receipt's move of the general product these units belong to (its purchase line, its price)
    move_id = fields.Many2one('stock.move', string='Receipt Line', required=True, ondelete='cascade',
                              domain="[('id', 'in', parent.move_ids)]")
    product_id = fields.Many2one(related='move_id.product_id', string='Livestock Product')
    weight = fields.Float(string="Weight (kg)", digits='Stock Weight', help="The weight of each of these units.")
    quantity = fields.Float(string="Quantity", default=1.0, digits='Product Unit of Measure',
                            help="How many units weighed this much.")
    total_weight = fields.Float(string="Total Weight (kg)", compute='_compute_band', digits='Stock Weight')
    band_id = fields.Many2one('livestock.variant.line', compute='_compute_band', string='Weight Band')
    received_product_id = fields.Many2one(related='band_id.product_id', string='Product Variant')
    price_per_kg = fields.Float(compute='_compute_band', string='Price / kg')
    amount = fields.Float(compute='_compute_band', string='Amount')

    @api.depends('weight', 'quantity', 'move_id')
    def _compute_band(self):
        Band = self.env['livestock.variant.line']
        for line in self:
            line.band_id = Band._find_band(line.product_id, line.weight) if line.product_id and line.weight > 0 else Band
            line.total_weight = line.weight * line.quantity
            line.price_per_kg = line.move_id._livestock_price_per_kg() if line.move_id else 0.0
            line.amount = line.total_weight * line.price_per_kg
