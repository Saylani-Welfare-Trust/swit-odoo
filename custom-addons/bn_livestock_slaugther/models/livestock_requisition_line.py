from odoo import models, fields


class LiveStockRequisitionLine(models.Model):
    _name = 'livestock.requisition.line'
    _description = 'Livestock Requisition Line'


    livestock_requisition_id = fields.Many2one('livestock.requisition', string="Livestock Requisition")
    product_id = fields.Many2one('product.product', string="Product")
    uom_id = fields.Many2one(related='product_id.uom_id', string="UOM")

    quantity = fields.Float('Quantity')