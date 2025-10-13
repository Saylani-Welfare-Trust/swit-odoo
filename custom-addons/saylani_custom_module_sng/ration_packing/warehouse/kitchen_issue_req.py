from odoo import models, fields, api

class WarehouseKitchenRequest(models.Model):
    _name = 'warehouse.kitchen.request'
    _description = 'Warehouse to Kitchen Request'

    name = fields.Char(string='Request Reference', required=True, copy=False, readonly=True, default='New')
    date = fields.Date(string='Request Date', default=fields.Date.context_today)
    warehouse_id = fields.Many2one('stock.location', string='Warehouse')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('done', 'Completed'),
    ], default='draft', string='Status')

    line_ids = fields.One2many(
        comodel_name='warehouse.kitchen.request.line',
        inverse_name='request_id',
        string='Lines',
    )

    kitchen_request_id = fields.Integer(
        string=' kitchen_request_id',
        required=False)

    res_id = fields.Integer(
        string=' res_id',
        required=False)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('warehouse.kitchen.request') or 'New'
        return super().create(vals)

    def action_send(self):
        self.write({'state': 'sent'})
        for line in self.line_ids:
            line.action_transfer_to_kitchen()
        return True

class WarehouseKitchenRequestLine(models.Model):
    _name = 'warehouse.kitchen.request.line'
    _description = 'Warehouse Kitchen Request Line'

    request_id = fields.Many2one(
        comodel_name='warehouse.kitchen.request',
        string='Request',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        required=True,
    )
    quantity = fields.Float(
        string='Quantity',
        required=True,
    )
    uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='Unit of Measure',
        required=True,
    )
    dest_location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Destination (Kitchen)',
        required=True,
    )

    def action_transfer_to_kitchen(self):

        warehouse_location = self.env['stock.location'].search([('usage', '=', 'internal'), ('name', 'ilike', 'warehouse')], limit=1)
        kitchen_obj = self.env['kitchen.daily.request'].browse(self.request_id.res_id)


        picking_type = self.env.ref('stock.picking_type_internal')
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': warehouse_location.id,
            'location_dest_id': self.dest_location_id.id,
            'origin': self.request_id.name,
            'move_ids_without_package': [
                (0, 0, {
                    'name': self.product_id.name,
                    'product_id': self.product_id.id,
                    'product_uom_qty': self.quantity,
                    'product_uom': self.uom_id.id,
                    'location_id': warehouse_location.id,
                    'location_dest_id': self.dest_location_id.id,
                }),
            ],
        })
        picking.action_confirm()


        kitchen_obj.write({'state': 'issued'})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }