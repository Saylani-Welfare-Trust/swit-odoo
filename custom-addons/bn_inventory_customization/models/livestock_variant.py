from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class LiveStockWeightBand(models.Model):
    """One weight band of a general livestock product (e.g. "Cow"): a unit of
    `purchase_product_id` weighing from `from_kg` (included) up to `to_kg`
    (excluded) is received as the product variant `product_id` (e.g. "Cow - 12").

    The Purchase Order and the Material Request use the general product; on the
    receipt, Receive by Weight distributes its units over the product variants
    of their weight."""
    _name = 'livestock.variant.line'
    _description = 'Livestock Weight Band'
    _order = 'purchase_product_id, from_kg, id'

    purchase_product_id = fields.Many2one(
        'product.product', string='Livestock Product', required=True, index=True, ondelete='cascade',
        domain=[('check_stock', '=', True)],
        help="The general product bought and requested (Is Livestock Product), before it is weighed.")
    purchase_template_id = fields.Many2one(
        related='purchase_product_id.product_tmpl_id', store=True, index=True, string='Livestock Product Template')
    from_kg = fields.Float(string='From (kg)', required=True, digits='Stock Weight',
                           help="Included: a unit of exactly this weight is in this band.")
    to_kg = fields.Float(string='To (kg)', required=True, digits='Stock Weight',
                         help="Excluded: a unit of exactly this weight is in the next band.")
    product_id = fields.Many2one(
        'product.product', string='Product Variant', required=True, ondelete='restrict',
        domain="[('type', '=', 'product'), ('id', '!=', purchase_product_id)]",
        help="The product (variant) a unit of this weight enters stock as.")
    company_id = fields.Many2one(related='product_id.company_id')

    @api.constrains('from_kg', 'to_kg')
    def _check_band(self):
        for band in self:
            if band.from_kg < 0 or float_compare(band.from_kg, band.to_kg, precision_digits=3) >= 0:
                raise ValidationError(_(
                    "%(product)s: the band must go up (from %(from)s kg to %(to)s kg).",
                    product=band.purchase_product_id.display_name, **{'from': band.from_kg, 'to': band.to_kg}))

    @api.constrains('purchase_product_id', 'from_kg', 'to_kg')
    def _check_no_overlap(self):
        for band in self:
            others = self.search([
                ('id', '!=', band.id),
                ('purchase_product_id', '=', band.purchase_product_id.id),
                ('from_kg', '<', band.to_kg),
                ('to_kg', '>', band.from_kg),
            ], limit=1)
            if others:
                raise ValidationError(_(
                    "%(product)s: %(from)s-%(to)s kg overlaps %(ofrom)s-%(oto)s kg. "
                    "A weight must fall in one band only.",
                    product=band.purchase_product_id.display_name,
                    ofrom=others.from_kg, oto=others.to_kg, **{'from': band.from_kg, 'to': band.to_kg}))

    @api.constrains('purchase_product_id', 'product_id')
    def _check_products(self):
        for band in self:
            if not band.purchase_product_id.check_stock:
                raise ValidationError(_(
                    "%s is not a livestock product: tick \"Is Livestock Product\" on it first.",
                    band.purchase_product_id.display_name))
            if band.product_id == band.purchase_product_id:
                raise ValidationError(_(
                    "%s: a unit is received as a product variant, not as the general product itself.",
                    band.purchase_product_id.display_name))

    @api.model
    def _find_band(self, purchase_product, weight):
        """The band a unit of `purchase_product` weighing `weight` kg falls in
        (empty when none)."""
        return self.search([
            ('purchase_product_id', '=', purchase_product.id),
            ('from_kg', '<=', weight),
            ('to_kg', '>', weight),
        ], limit=1)

    @api.model
    def _max_weight(self, purchase_product):
        """The heaviest configured weight of a livestock product: what a unit is
        estimated at on the Purchase Order before it is weighed."""
        bands = self.search([('purchase_product_id', '=', purchase_product.id)])
        return max(bands.mapped('to_kg') or [0.0])
