from odoo import models, fields


class ResUser(models.Model):
    _inherit = 'res.users'


    allowed_location_ids = fields.Many2many('stock.location', string="Allowed Location")
    allowed_warehouse_ids = fields.Many2many('stock.warehouse', string="Allowed Warehouses")