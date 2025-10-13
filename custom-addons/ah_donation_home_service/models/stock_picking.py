from odoo import fields,api,models

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_donation_home_service = fields.Boolean()
    dhs_id = fields.Many2one('donation.home.service', 'DHS ID')
    is_dhs_returned = fields.Boolean()

    def action_receive_product(self):
        picking = self.env['stock.picking'].create({
            'partner_id': self.partner_id.id,
            'picking_type_id': self.env.ref('stock.picking_type_in').id,
            'origin':  f'Receive Against {self.origin}',
            'is_donation_home_service': True,
            'dhs_id': self.dhs_id.id
        })

        for line in self.move_ids_without_package:
            if line.product_id.detailed_type == 'product':
                return_product_conf = self.env['dhs.product.conf'].sudo().search([
                    ('product_id', '=', line.product_id.id)
                ], limit=1)

                stock_move = self.env['stock.move'].create({
                    'name': f'Receive Against {self.origin}',
                    'product_id': return_product_conf.return_product_id.id,
                    'product_uom': line.product_id.uom_id.id,
                    'product_uom_qty': line.quantity,
                    'location_id': self.env.ref('stock.stock_location_customers').id,
                    'location_dest_id': self.env.ref('stock.stock_location_stock').id,
                    'state': 'draft',
                    'picking_id': picking.id
                })

        for move in picking.move_ids:
            move._action_confirm()
            move._action_assign()

        picking.action_confirm()
        picking.button_validate()

        self.write({'is_dhs_returned': True})
        picking.write({'is_dhs_returned': True})

        return {
            'type': 'ir.actions.act_window',
            'name': 'Stock Picking',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
            'target': 'current',
        }


    def action_cancel_order(self):
        picking = self.env['stock.picking'].create({
            'partner_id': self.partner_id.id,
            'picking_type_id': self.env.ref('stock.picking_type_in').id,
            'origin':  f'Receive Against {self.origin}',
            'is_donation_home_service': True,
            'dhs_id': self.dhs_id.id
        })

        for line in self.move_ids_without_package:
            if line.product_id.detailed_type == 'product':
                stock_move = self.env['stock.move'].create({
                    'name': f'Receive Against {self.origin}',
                    'product_id': line.product_id.id,
                    'product_uom': line.product_id.uom_id.id,
                    'product_uom_qty': line.quantity,
                    'location_id': self.env.ref('stock.stock_location_customers').id,
                    'location_dest_id': self.env.ref('stock.stock_location_stock').id,
                    'state': 'draft',
                    'picking_id': picking.id
                })

        for move in picking.move_ids:
            move._action_confirm()
            move._action_assign()

        picking.action_confirm()
        picking.button_validate()
        picking.dhs_id.cancel_donation()

        self.write({'is_dhs_returned': True})
        picking.write({'is_dhs_returned': True})

        return {
            'type': 'ir.actions.act_window',
            'name': 'Stock Picking',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
            'target': 'current',
        }