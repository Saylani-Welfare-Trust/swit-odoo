from odoo import fields, models, api

class PosRegisteredOrderLine(models.Model):
    _name="pos.registered.order.line"

    name=fields.Char(string="Name")
    product_id=fields.Many2one('product.product',string="Product")
    product_tmpl_id=fields.Many2one('product.template',string="Product",related="product_id.product_tmpl_id")
    qty=fields.Integer(string="Quantity",default=1)
    price_unit=fields.Float(string="Unit Price")
    price_subtotal=fields.Float(string="Subtotal",compute="_compute_subtotal")
    order_id=fields.Many2one('pos.registered.order',string="Order")
    
    @api.depends('qty','price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal=line.qty*line.price_unit
    
    
    