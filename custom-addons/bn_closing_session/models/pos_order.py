from odoo import models, fields, api


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'


    product_category_id = fields.Many2one(
        related='product_id.categ_id',
        string='Product Category',
        store=True
    )