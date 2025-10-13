from odoo import models, fields, api
from odoo.exceptions import UserError


class live_stock_slaughter_cutting(models.Model):
    _name = 'live_stock_slaughter.cutting'
    _description = 'live_stock_slaughter.cutting'
    _rec_company_auto = True

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    product = fields.Many2one('product.product', string="Product", required=True)

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

    picking_id = fields.Many2one('stock.picking', string="Picking")

    state = fields.Selection(
        string='State',
        selection=[('not_received', 'Not Received'),
                   ('received', 'Received'), ],
        default='not_received',
        required=False, )


    def action_confirm(self):
        for record in self:
            record.confirm_hide = True
            record.state = 'received'


    def action_validate_picking(self):
        for record in self:
            cutting_obj = self.env['live_stock_slaughter.cutting_material']
            product_pro = self.product

            print('nameeee', product_pro.id)

            cutting_record = cutting_obj.create({
                'product': record.product.id,
                'quantity': record.quantity,
                'price': record.price,
                'product_code': record.product_code,
            })

            if not record.picking_id:
                raise UserError("No picking linked to this cutting record!")

            # Find the move line or create one manually
            # if not record.picking_id.move_ids_without_package:
            #
            #     print('hellllll')
            #     # Create a stock move manually
            #     self.env['stock.move'].create({
            #         'name': product_pro.name,
            #         'product_id': product_pro.id,
            #         'product_uom_qty': record.quantity,
            #         'quantity': record.quantity,
            #         'product_uom': product_pro.uom_id.id,
            #         'picking_id': record.picking_id.id,
            #         'location_id': record.picking_id.location_id.id,
            #         'location_dest_id': record.picking_id.location_dest_id.id,
            #     })
            #     record.picking_id.action_assign()

            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
                ('warehouse_id.company_id', '=', self.env.company.id)
            ], limit=1)

            cutting_location = self.env['stock.location'].search([('name', '=', 'Cutting')], limit=1)
            slaughter_location = self.env['stock.location'].search([('name', '=', 'Slaughter Stock')], limit=1)
            if not cutting_location:
                raise UserError(
                    "Slaughter Stock location not found. Please create it in Inventory > Configuration > Locations.")

            if not picking_type:
                raise UserError(
                    "Internal Transfer operation type not found. Please configure it in Inventory > Configuration > Operation Types.")

            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': slaughter_location.id,
                'location_dest_id': cutting_location.id,
                'origin': self.product or 'Live Stock Slaughter',
            })

            # Create the stock move
            move = self.env['stock.move'].create({
                'name': product_pro.display_name,
                'product_id': product_pro.id,
                'product_uom_qty': self.quantity,
                'quantity': self.quantity,
                'product_uom': product_pro.uom_id.id,
                'picking_id': picking.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
            })

            print('moveeee', move)

            # Confirm and assign the picking
            picking.action_confirm()
            picking.action_assign()
            picking.button_validate()

            # Set quantity_done
            # for move_line in record.picking_id.move_line_ids:
            #     move_line.quantity_done = record.quantity

            # Validate the picking
            # record.picking_id.button_validate()
            record.cutting_hide = True

            return {
                'type': 'ir.actions.act_window',
                'name': 'Cutting Material Record',
                'res_model': 'live_stock_slaughter.cutting_material',
                'res_id': cutting_record.id,
                'view_mode': 'form',
                'target': 'current',
            }
