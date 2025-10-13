from odoo import models, api
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def create(self, vals):
        order = super(PosOrder, self).create(vals)

        # Manually search for the 'Cutting' location
        cutting_location = self.env['stock.location'].search([('name', '=', 'Slaughter Stock')], limit=1)
        if not cutting_location:
            raise UserError("Cutting location not found. Please create a stock location named 'Slaughter Stock'.")

        for line in order.lines:
            product = line.product_id
            quantity = line.qty
            price = line.price_subtotal_incl

            # Create a record in live_stock_slaughter model
            self.env['live_stock_slaughter.live_stock_slaughter'].create({
                'product': product.product_tmpl_id.id,
                'product_code': product.default_code,
                'quantity': quantity,
                'price': price,
            })

            # Get source location (warehouse stock location)
            source_location = order.session_id.config_id.warehouse_id.lot_stock_id
            if not source_location:
                source_location = order.company_id.warehouse_id.lot_stock_id

            # Create a stock picking
            picking = self.env['stock.picking'].create({
                'picking_type_id': self.env['stock.picking.type'].search([('code', '=', 'internal')], limit=1).id,
                'location_id': source_location.id,
                'location_dest_id': cutting_location.id,
                'origin': order.name,
            })

            # Create stock move
            move = self.env['stock.move'].create({
                'name': product.name,
                'product_id': product.id,
                'product_uom_qty': quantity,
                'quantity': quantity,
                'product_uom': product.uom_id.id,
                'picking_id': picking.id,
                'location_id': source_location.id,
                'location_dest_id': cutting_location.id,
            })

            # Reserve stock and set quantity done
            picking.action_assign()
            # for move_line in picking.move_line_ids:
            #     move_line.quantity_done = quantity

            # Validate the picking
            picking.button_validate()

        return order


