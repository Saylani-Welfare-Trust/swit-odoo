from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class LiveStockVariant(models.Model):
    """What a livestock unit is bought for (Sadqa, Aqiqa, Qurbani ...). For each
    purchase product it lists the weight bands, and the product each weighed
    unit is received into stock as."""
    _name = 'livestock.variant'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Livestock Variant'
    _order = 'name'

    name = fields.Char(string='Name', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    line_ids = fields.One2many('livestock.variant.line', 'variant_id', string='Weight Bands', copy=True)
    purchase_product_ids = fields.Many2many(
        'product.product', string='Purchase Products', compute='_compute_purchase_product_ids')

    _sql_constraints = [('name_unique', 'unique(name)', 'This livestock variant already exists.')]

    @api.depends('line_ids.purchase_product_id')
    def _compute_purchase_product_ids(self):
        for variant in self:
            variant.purchase_product_ids = variant.line_ids.purchase_product_id


class LiveStockVariantLine(models.Model):
    """One weight band: a unit of `purchase_product_id` bought for `variant_id`
    and weighing from `from_kg` (included) up to `to_kg` (excluded) is received
    as `product_id`."""
    _name = 'livestock.variant.line'
    _description = 'Livestock Weight Band'
    _order = 'variant_id, purchase_product_id, from_kg, id'

    variant_id = fields.Many2one('livestock.variant', string='Livestock Variant', required=True,
                                 ondelete='cascade', index=True)
    purchase_product_id = fields.Many2one(
        'product.product', string='Purchase Product', required=True, index=True, ondelete='restrict',
        domain=[('check_stock', '=', True), ('purchase_ok', '=', True)],
        help="The product bought on the Purchase Order (by unit), before it is weighed.")
    purchase_template_id = fields.Many2one(
        related='purchase_product_id.product_tmpl_id', store=True, index=True, string='Purchase Product Template')
    from_kg = fields.Float(string='From (kg)', required=True, digits='Stock Weight',
                           help="Included: a unit of exactly this weight is in this band.")
    to_kg = fields.Float(string='To (kg)', required=True, digits='Stock Weight',
                         help="Excluded: a unit of exactly this weight is in the next band.")
    product_id = fields.Many2one(
        'product.product', string='Received As', required=True, ondelete='restrict',
        domain=[('type', '=', 'product')],
        help="The product (category) the weighed unit enters stock as.")
    company_id = fields.Many2one(related='product_id.company_id')

    @api.constrains('from_kg', 'to_kg')
    def _check_band(self):
        for band in self:
            if band.from_kg < 0 or float_compare(band.from_kg, band.to_kg, precision_digits=3) >= 0:
                raise ValidationError(_(
                    "%(variant)s / %(product)s: the band must go up (from %(from)s kg to %(to)s kg).",
                    variant=band.variant_id.name, product=band.purchase_product_id.display_name,
                    **{'from': band.from_kg, 'to': band.to_kg}))

    @api.constrains('variant_id', 'purchase_product_id', 'from_kg', 'to_kg')
    def _check_no_overlap(self):
        for band in self:
            others = self.search([
                ('id', '!=', band.id),
                ('variant_id', '=', band.variant_id.id),
                ('purchase_product_id', '=', band.purchase_product_id.id),
                ('from_kg', '<', band.to_kg),
                ('to_kg', '>', band.from_kg),
            ], limit=1)
            if others:
                raise ValidationError(_(
                    "%(variant)s / %(product)s: %(from)s-%(to)s kg overlaps %(ofrom)s-%(oto)s kg. "
                    "A weight must fall in one band only.",
                    variant=band.variant_id.name, product=band.purchase_product_id.display_name,
                    ofrom=others.from_kg, oto=others.to_kg, **{'from': band.from_kg, 'to': band.to_kg}))

    @api.constrains('purchase_product_id')
    def _check_purchase_product(self):
        for band in self:
            if not band.purchase_product_id.check_stock:
                raise ValidationError(_(
                    "%s is not a livestock product: tick \"Is Livestock Product\" on it first.",
                    band.purchase_product_id.display_name))

    @api.model
    def _find_band(self, variant, purchase_product, weight):
        """The band a unit of `purchase_product` bought for `variant` and
        weighing `weight` kg falls in (empty when none)."""
        return self.search([
            ('variant_id', '=', variant.id),
            ('purchase_product_id', '=', purchase_product.id),
            ('from_kg', '<=', weight),
            ('to_kg', '>', weight),
        ], limit=1)

    @api.model
    def _max_weight(self, purchase_product):
        """The heaviest configured weight of a purchase product: what a unit is
        estimated at on the Purchase Order before it is weighed."""
        bands = self.search([('purchase_product_id', '=', purchase_product.id)])
        return max(bands.mapped('to_kg') or [0.0])
