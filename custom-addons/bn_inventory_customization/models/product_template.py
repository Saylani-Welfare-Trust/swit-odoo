from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    check_stock = fields.Boolean(
        string='Is Livestock Product',
        default=False,
        tracking=True,
        help='Enable weight-based receiving for livestock products. '
             'When checked, this product will use the Receive by Weight wizard.'
    )
    
    livestock_variant = fields.Many2one(
        comodel_name='livestock.variant',
        string='Livestock Variant',
        required=False
    )

    purchase_product = fields.Many2one(
        comodel_name='product.product',
        relation='livestock_product',
        string='Purchase Product',
        help='Product you will make PO',
        required=False
    )

    main_attribute_id = fields.Many2one(
        comodel_name='product.attribute',
        string='Main Attribute',
        help='When set, only this attribute\'s values are used to determine the highest to_kg.'
    )