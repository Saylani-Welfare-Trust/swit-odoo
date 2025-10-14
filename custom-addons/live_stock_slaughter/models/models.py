from odoo import models, fields, api
from odoo.exceptions import UserError


class live_stock_slaughter(models.Model):
    _name = 'live_stock_slaughter.live_stock_slaughter'
    _description = 'live_stock_slaughter.live_stock_slaughter'
    _rec_company_auto = True

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    product = fields.Many2one('product.template', string="Product", required=True)


    quantity = fields.Integer(
        string='Quantity',
    )

    price = fields.Float(
        string='Price',
    )


    product_code = fields.Char(
        string='Product Code',
        required=False)


    confirm_hide = fields.Boolean(
        string='Confirm_hide',
        required=False)

    cutting_hide = fields.Boolean(
        string='Confirm_hide',
        required=False)

    state = fields.Selection(
        string='State',
        selection=[('not_received', 'Not Received'),
                   ('received', 'Received'), ],
        default='not_received',
        required=False, )


    def action_confirm(self):
        # Retrieve the 'Slaughter Stock' location
        slaughter_location = self.env['stock.location'].search([('name', '=', 'Slaughter Stock')], limit=1)
        if not slaughter_location:
            raise UserError(
                "Slaughter Stock location not found. Please create it in Inventory > Configuration > Locations.")

        # Retrieve the internal transfer operation type
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.env.company.id)
        ], limit=1)
        if not picking_type:
            raise UserError(
                "Internal Transfer operation type not found. Please configure it in Inventory > Configuration > Operation Types.")

        # Retrieve the product based on the product code
        product = self.env['product.product'].search([('default_code', '=', self.product_code)], limit=1)
        if not product:
            raise UserError(f"Product with code '{self.product_code}' not found.")

        # Create the stock picking
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': slaughter_location.id,
            'origin': self.product or 'Live Stock Slaughter',
        })

        # Create the stock move
        move = self.env['stock.move'].create({
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

        return True


    def action_cutting(self):
        # Retrieve the 'Slaughter Stock' location
        cutting_obj = self.env['live_stock_slaughter.cutting']

        slaughter_location = self.env['stock.location'].search([('name', '=', 'Cutting')], limit=1)
        if not slaughter_location:
            raise UserError(
                "Cutting location not found. Please create it in Inventory > Configuration > Locations.")

        # Retrieve the internal transfer operation type
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.env.company.id)
        ], limit=1)
        if not picking_type:
            raise UserError(
                "Internal Transfer operation type not found. Please configure it in Inventory > Configuration > Operation Types.")

        # Retrieve the product based on the product code
        product = self.env['product.product'].search([('default_code', '=', self.product_code)], limit=1)
        if not product:
            raise UserError(f"Product with code '{self.product_code}' not found.")

        # Create the stock picking
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': slaughter_location.id,
            'origin': self.product.id or '',
        })

        # Create the stock move
        move = self.env['stock.move'].create({
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
            'product': self.product.id,
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


