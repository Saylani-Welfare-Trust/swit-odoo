from odoo import models, fields
from odoo.exceptions import ValidationError


state_selection = [
    ('not_received', 'Not Received'),
    ('received', 'Received')
]


class LivestockSlaughter(models.Model):
    _name = 'livestock.slaugther'
    _description = "Livestock Slaugther"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    donee_id = fields.Many2one('res.partner', string="Donee")
    product_id = fields.Many2one('product.product', string="Product")
    location_id = fields.Many2one('stock.location', string="Location")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)

    name = fields.Char(related='product_id.name', string="Product Name", store=True)
    code = fields.Char(related='product_id.default_code', string="Product Code", store=True)
    ref = fields.Char('Source Document')

    quantity = fields.Integer('Quantity', default=1)

    price = fields.Monetary('Price', currency_field='currency_id', default=0)

    state = fields.Selection(selection=state_selection, string="State", default='not_received')


    def action_confirm(self):
        # Retrieve the 'Slaughter Stock' location

        slaughter_location = self.env['stock.location'].search([('name', '=', 'Slaughter Stock')], limit=1)
        if not slaughter_location:
            raise ValidationError("Slaughter Stock location not found. Please create it in Inventory > Configuration > Locations.")

        # Retrieve the internal transfer operation type
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.env.company.id)
        ], limit=1)
        if not picking_type:
            raise ValidationError("Internal Transfer operation type not found. Please configure it in Inventory > Configuration > Operation Types.")

        # Retrieve the product based on the product code
        product = self.product_new
        if not product:
            raise ValidationError(f"Product with code '{self.product_code}' not found.")

        if self.transfer_location:
            destination_location = self.transfer_location.id
        else:
            destination_location = slaughter_location.id

        # Create the stock picking
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': destination_location,
            'origin': self.product or 'Live Stock Slaughter',
        })

        # Create the stock move
        self.env['stock.move'].create({
            'name': product.display_name,
            'product_id': product.id,
            'product_uom_qty': self.quantity,
            'quantity': self.quantity,
            'product_uom': product.uom_id.id,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
        })

        # Confirm and assign the picking
        picking.action_confirm()
        picking.action_assign()

        # Set the done quantities and validate the picking
        for move_line in picking.move_line_ids:
            move_line.quantity = move_line.quantity_product_uom
        picking.button_validate()

        self.confirm_hide = True
        self.state = 'received'

    def action_cutting(self):
        # Retrieve the 'Slaughter Stock' location
        cutting_obj = self.env['live_stock_slaughter.cutting']

        slaughter_location = self.env['stock.location'].search([('name', '=', 'Livestock Cutting')], limit=1)
        if not slaughter_location:
            raise ValidationError("Livestock Cutting location not found. Please create it in Inventory > Configuration > Locations.")

        # Retrieve the internal transfer operation type
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.env.company.id)
        ], limit=1)
        if not picking_type:
            raise ValidationError("Internal Transfer operation type not found. Please configure it in Inventory > Configuration > Operation Types.")

        # Retrieve the product based on the product code
        product = self.product_new


        # Create the stock picking
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': slaughter_location.id,
            'origin': self.product_new.id or '',
        })

        # Create the stock move
        self.env['stock.move'].create({
            'name': product.display_name,
            'product_id': product.id,
            'product_uom_qty': self.quantity,
            'quantity': self.quantity,
            'product_uom': product.uom_id.id,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
        })

        # Confirm and assign the picking
        picking.action_confirm()
        picking.action_assign()

        # Set the done quantities and validate the picking
        # for move_line in picking.move_line_ids:
        #     move_line.quantity = move_line.quantity_product_uom
        picking.button_validate()
        cutting_record = cutting_obj.create({
            'product_new': self.product_new.id,
            'quantity': self.quantity,
            'price': self.price,
            'product_code': self.product_code,
            'picking_id': picking.id,
        })

        self.cutting_hide = True

        return {
            'type': 'ir.actions.act_window',
            'name': 'Cutting Record',
            'res_model': 'live_stock_slaughter.cutting',
            'res_id': cutting_record.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_open_wizard(self):
        """Open a transient wizard to choose destination location"""
        
        self.ensure_one()
        
        return {
            'name': _('Transfer from Slaughter Stock'),
            'type': 'ir.actions.act_window',
            'res_model': 'livestock.slaugther.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_livestock_slaughter_id': self.id},
        }