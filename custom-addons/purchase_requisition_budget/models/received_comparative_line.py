from odoo import models, fields, api
from odoo.exceptions import UserError


class ReceivedComparative(models.Model):
    _name = 'received.comparative.line'

    received_id = fields.Many2one(comodel_name='purchase.order', string="Comparative")
    vendor_id = fields.Many2one(comodel_name='res.partner', string="Vendor", domain=[('supplier_rank', '>', 0)])
    # product_id = fields.Many2one(comodel_name='product.product', string="Product")
    product_ids = fields.Many2many(comodel_name='product.product', string="Product")
    quantity = fields.Float(string="Quantity", required=True, default=1.0)
    price_unit = fields.Float(string="Unit Price",)
    is_selected = fields.Boolean(string="Select for PO")
    po_id = fields.Many2one(comodel_name='purchase.order', string="Generated PO", readonly=True)
