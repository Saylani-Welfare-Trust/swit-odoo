from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'

    check_stock = fields.Boolean(
        related='product_tmpl_id.check_stock',
        string='Is Livestock Product',
        store=True,
        readonly=False,
        tracking=True
    )
