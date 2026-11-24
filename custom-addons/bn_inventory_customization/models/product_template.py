from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    check_stock = fields.Boolean(
        string='Is Livestock Product',
        default=False,
        tracking=True,
        help='Bought by unit and received by weight: on its receipt each unit is weighed '
             'and received as the product of its weight band (Livestock Variants).')
    # the weight bands this product is the purchase product of (Livestock page)
    livestock_band_ids = fields.One2many(
        'livestock.variant.line', 'purchase_template_id', string='Weight Bands')
