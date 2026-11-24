from odoo import api, fields, models


class ReceiveByWeightLine(models.TransientModel):
    _name = 'receive.by.weight.line'
    _description = "Receive By Weight Line"
    _order = 's_no, id'

    s_no = fields.Integer(string="S.No")
    wizard_id = fields.Many2one('receive.by.weight', required=True, ondelete='cascade')
    # the receipt's move of the purchase product this unit belongs to (its purchase line, its price)
    move_id = fields.Many2one('stock.move', string='Receipt Line', required=True, ondelete='cascade')
    product_id = fields.Many2one(related='move_id.product_id', string='Purchase Product')
    livestock_variant = fields.Many2one(
        'livestock.variant', string='Livestock Variant',
        domain="[('line_ids.purchase_product_id', '=', product_id)]")
    weight = fields.Float(string="Weight (kg)", digits='Stock Weight')
    band_id = fields.Many2one('livestock.variant.line', compute='_compute_band', string='Weight Band')
    received_product_id = fields.Many2one(related='band_id.product_id', string='Received As')
    price_per_kg = fields.Float(compute='_compute_band', string='Price / kg')
    amount = fields.Float(compute='_compute_band', string='Amount')

    @api.depends('livestock_variant', 'weight', 'move_id')
    def _compute_band(self):
        Band = self.env['livestock.variant.line']
        for line in self:
            line.band_id = Band._find_band(line.livestock_variant, line.product_id, line.weight) \
                if line.livestock_variant and line.weight > 0 else Band
            line.price_per_kg = line.move_id._livestock_price_per_kg() if line.move_id else 0.0
            line.amount = line.weight * line.price_per_kg
