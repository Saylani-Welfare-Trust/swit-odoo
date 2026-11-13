from odoo import models, fields


class ResUser(models.Model):
    _inherit = 'res.users'


    allowed_location_ids = fields.Many2many('stock.location', string="Allowed Location")
    allowed_warehouse_ids = fields.Many2many('stock.warehouse', string="Allowed Warehouses")
    allowed_product_category_ids = fields.Many2many('product.category', string="Allowed Categories")

    def _get_invalidation_fields(self):
        # Record rules read these fields, and rule domains are cached per user:
        # changing them must drop that cache or the old access stays until restart.
        return super()._get_invalidation_fields() | {'allowed_location_ids', 'allowed_warehouse_ids'}
