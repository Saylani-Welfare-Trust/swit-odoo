from odoo import models, fields, api
from odoo.exceptions import UserError


class live_stock_slaughter_cutting(models.Model):
    _name = 'live_stock_slaughter.cutting'
    _description = 'live_stock_slaughter.cutting'
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

    def action_validate_picking22(self):
        for record in self:
            cutting_obj = self.env['live_stock_slaughter.cutting_material']

            product_pro = self.env['product.product'].search([('product_tmpl_id', '=', record.product.id)])

            print('product', product_pro.name)

            # Create the cutting material record
            cutting_obj.create({
                'product': product_pro.id,
                'quantity': record.quantity,
                'price': record.price,
                'product_code': record.product_code,
            })

            # Check Picking
            if not record.picking_id:
                raise UserError("No picking linked to this cutting record!")

            # Set done quantities manually before validating
            # for move_line in record.picking_id.move_line_ids:
            #     move_line.quantity = move_line.quantity_product_uom  # Mark all reserved quantities as done

            # Now safe to validate
            record.picking_id.button_validate()

            # Hide the cutting button
            record.cutting_hide = True

    def action_validate_picking(self):
        for record in self:
            cutting_obj = self.env['live_stock_slaughter.cutting_material']
            product_pro = self.env['product.product'].search([('product_tmpl_id', '=', record.product.id)], limit=1)

            cutting_record = cutting_obj.create({
                'product': product_pro.id,
                'quantity': record.quantity,
                'price': record.price,
                'product_code': record.product_code,
            })

            if not record.picking_id:
                raise UserError("No picking linked to this cutting record!")

            # Find the move line or create one manually
            if not record.picking_id.move_ids_without_package:
                # Create a stock move manually
                self.env['stock.move'].create({
                    'name': product_pro.name,
                    'product_id': product_pro.id,
                    'product_uom_qty': record.quantity,
                    'quantity': record.quantity,
                    'product_uom': product_pro.uom_id.id,
                    'picking_id': record.picking_id.id,
                    'location_id': record.picking_id.location_id.id,
                    'location_dest_id': record.picking_id.location_dest_id.id,
                })
                record.picking_id.action_assign()

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
