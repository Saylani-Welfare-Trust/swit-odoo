from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.populate import compute


class PurchaseComparative(models.Model):
    _name = 'purchase.comparative.line'

    comparative_id = fields.Many2one(comodel_name='purchase.order', string="Comparative")
    vendor_id = fields.Many2one(comodel_name='res.partner', string="Vendor", domain=[('supplier_rank', '>', 0)])
    # product_id = fields.Many2one(comodel_name='product.product', string="Product")
    product_ids = fields.Many2many(comodel_name='product.product',
                                  relation='purchase_comparative_product_rel',
                                  column1='comparative_id',
                                  column2='product_id', string="Product",
                                  compute="_compute_product_ids", store=True, readonly=False)
    quantity = fields.Float(string="Quantity", compute="_compute_product_ids" ,store=True,readonly=False,required=True, default=1.0)
    # price_unit = fields.Float(string="Unit Price")
    is_selected = fields.Boolean(string="Select for PO")
    po_id = fields.Many2one(comodel_name='purchase.order', string="Generated PO", readonly=True)

    @api.depends('comparative_id.order_line')
    def _compute_product_ids(self):
        for record in self:
            if record.comparative_id:
                order_lines = record.comparative_id.order_line
                # Order line se products aur quantity set karna
                products = order_lines.mapped('product_id')
                record.product_ids = [(6, 0, products.ids)]
                record.quantity = sum(order_lines.mapped('product_qty'))
            else:
                record.product_ids = [(5, 0, 0)]  # Clear products
                record.quantity = 0.0

    @api.constrains('product_ids')
    def _compute_total_quantity(self):
        for rec in self:
            total_qty = 0.0
            if rec.comparative_id:
                total_qty = sum(
                    self.env['purchase.order.line'].search([
                        ('order_id', '=', rec.comparative_id.id),
                        ('product_id', 'in', rec.product_ids.ids)
                    ]).mapped('product_qty')
                )
            rec.quantity = total_qty
