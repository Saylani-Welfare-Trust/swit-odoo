from odoo import models, fields
from odoo.exceptions import ValidationError


state_selection = [
    ('not_received', 'Not Received'),
    ('received', 'Received')
]


class LivestockCutting(models.Model):
    _name = 'livestock.cutting'
    _description = "Livestock Cutting"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    product_id = fields.Many2one('product.product', string="Product")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)

    name = fields.Char(related='product_id.name', string="Product Name", store=True)
    code = fields.Char(related='product_id.default_code', string="Product Code", store=True)

    quantity = fields.Integer('Quantity', default=1)

    price = fields.Monetary('Price', currency_field='currency_id', default=0)

    state = fields.Selection(selection=state_selection, string="State", default='not_received')


    def action_confirm(self):
        self.state = 'received'
    
    def action_validate_picking(self):
        cutting_obj = self.env['live_stock_slaughter.cutting_material']
        product_pro = self.product

        cutting_record = cutting_obj.create({
            'product': self.product.id,
            'quantity': self.quantity,
            'price': self.price,
            'product_code': self.product_code,
        })

        if not self.picking_id:
            raise ValidationError("No picking linked to this cutting record!")

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.env.company.id)
        ], limit=1)

        cutting_location = self.env['stock.location'].search([('name', '=', 'Livestock Cutting')], limit=1)
        slaughter_location = self.env['stock.location'].search([('name', '=', 'Livestock Slaugther')], limit=1)
        if not cutting_location:
            raise ValidationError("Slaughter Stock location not found. Please create it in Inventory > Configuration > Locations.")

        if not picking_type:
            raise ValidationError("Internal Transfer operation type not found. Please configure it in Inventory > Configuration > Operation Types.")

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': slaughter_location.id,
            'location_dest_id': cutting_location.id,
            'origin': self.product or 'Live Stock Slaughter',
        })

        # Create the stock move
        self.env['stock.move'].create({
            'name': product_pro.display_name,
            'product_id': product_pro.id,
            'product_uom_qty': self.quantity,
            'quantity': self.quantity,
            'product_uom': product_pro.uom_id.id,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
        })

        # Confirm and assign the picking
        picking.action_confirm()
        picking.action_assign()
        picking.button_validate()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Cutting Material Record',
            'res_model': 'live_stock_slaughter.cutting_material',
            'res_id': cutting_record.id,
            'view_mode': 'form',
            'target': 'current',
        }