from odoo import models, fields, api


class ProductPackaging(models.Model):
    _inherit = 'product.packaging'

    on_hand_qty = fields.Float(
        string='On Hand',
        compute='_compute_on_hand_qty'
    )

    on_hand_packages = fields.Float(
        string='On Hand (Packages)',
        compute='_compute_on_hand_qty'
    )

    @api.depends('product_id')
    def _compute_on_hand_qty(self):
        for rec in self:
            if rec.product_id:
                rec.on_hand_qty = rec.product_id.qty_available
                rec.on_hand_packages = (
                    rec.on_hand_qty / rec.qty if rec.qty else 0.0
                )
            else:
                rec.on_hand_qty = 0.0
                rec.on_hand_packages = 0.0