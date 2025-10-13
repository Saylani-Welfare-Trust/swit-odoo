from odoo import models, fields


class ProductParent(models.Model):
    _name = 'product.parent'
    _description = 'Product Parent'

    name = fields.Char(string="Reference", required=True, copy=False, default="New")
    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Main Product",
        required=True
    )
    line_ids = fields.One2many(
        comodel_name='product.parent.line',
        inverse_name='parent_id',
        string="Product Lines"
    )


class ProductParentLine(models.Model):
    _name = 'product.parent.line'
    _description = 'Product Parent Line'

    parent_id = fields.Many2one(
        comodel_name='product.parent',
        string="Parent",
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Line Product",
        required=True
    )
    quantity = fields.Float(string="Quantity", default=1.0)
