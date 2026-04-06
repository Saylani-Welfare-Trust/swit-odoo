from odoo import models, fields, _
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
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)

    name = fields.Char(related='product_id.name', string="Product Name", store=True)
    code = fields.Char(related='product_id.default_code', string="Product Code", store=True)
    ref = fields.Char('Source Document')

    quantity = fields.Integer('Quantity', default=1)

    price = fields.Monetary('Price', currency_field='currency_id', default=0)

    state = fields.Selection(selection=state_selection, string="State", default='not_received')

    is_meat_depart = fields.Boolean('Is Meat Department')
    is_goat_depart = fields.Boolean('Is Goat Department')
    confirm_hide = fields.Boolean('Confirm Hide')
    cutting_hide = fields.Boolean('Cutting Hide')


    def action_confirm(self):
        # Retrieve the 'Slaughter Stock' location
        location = None

        if self.is_meat_depart:
            location = self.env['stock.location'].search([('name', '=', 'Meat')], limit=1)
        elif self.is_goat_depart:
            location = self.env['stock.location'].search([('name', '=', 'Goat')], limit=1)
        else:
            location = self.env['stock.location'].search([('name', '=', 'Slaughter Stock')], limit=1)
        
        if not location:
            raise ValidationError("Slaughter Stock, Meat or Goat location not found. Please create it in Inventory > Configuration > Locations.")

        # Retrieve the internal transfer operation type
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.env.company.id)
        ], limit=1)
        if not picking_type:
            raise ValidationError("Internal Transfer operation type not found. Please configure it in Inventory > Configuration > Operation Types.")

        # Retrieve the product based on the product code
        product = self.product_id
        if not product:
            raise ValidationError(f"Product with code '{self.code}' not found.")

        # Create the stock picking
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': location.id,
            'origin': self.product_id or 'Live Stock Slaughter',
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
        cutting_obj = self.env['livestock.cutting']

        location = self.env['stock.location'].search([('name', '=', 'Livestock Cutting')], limit=1)
        if not location:
            raise ValidationError("Livestock Cutting location not found. Please create it in Inventory > Configuration > Locations.")

        # Retrieve the internal transfer operation type
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.env.company.id)
        ], limit=1)
        if not picking_type:
            raise ValidationError("Internal Transfer operation type not found. Please configure it in Inventory > Configuration > Operation Types.")

        # Retrieve the product based on the product code
        product = self.product_id


        # Create the stock picking
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': location.id,
            'origin': self.product_id.id or '',
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
        picking.button_validate()
        cutting_record = cutting_obj.create({
            'product_id': self.product_id.id,
            'quantity': self.quantity,
            'price': self.price,
            'code': self.code,
            'picking_id': picking.id,
        })

        self.cutting_hide = True

        return {
            'type': 'ir.actions.act_window',
            'name': 'Cutting Record',
            'res_model': 'livestock.cutting',
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