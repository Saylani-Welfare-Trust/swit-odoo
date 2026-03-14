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
    
    livestock_variant = fields.Many2one(
        related='product_tmpl_id.livestock_variant',
        string='Livestock Variant',
        store=True,
        readonly=False
    )

    purchase_product = fields.Many2one(
        related='product_tmpl_id.purchase_product',
        string='Purchase Product',
        store=True,
        readonly=False
    )

    main_attribute_id = fields.Many2one(
        related='product_tmpl_id.main_attribute_id',
        string='Main Attribute',
        store=True,
        readonly=False
    )