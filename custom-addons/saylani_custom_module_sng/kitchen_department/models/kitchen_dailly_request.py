from odoo import models, fields, api
from datetime import date, datetime

from odoo.exceptions import UserError


class KitchenDailyRequest(models.Model):
    _name = 'kitchen.daily.request'
    _description = 'Kitchen Daily Request'

    date = fields.Date(string='Date', required=True)
    branch_id = fields.Many2one('res.company', string='Branch', required=True)
    request_line_ids = fields.One2many('kitchen.daily.request.line', 'daily_request_id', string='Requested Items')


    state = fields.Selection(
        string='State',
        selection=[('request', 'Requested from Warehouse'),
                   ('issued', 'Issued'), ],
        required=False, )


    def action_manufacture(self):

        Production = self.env['mrp.production']
        BomModel    = self.env['mrp.bom']
        kitchen_loc = self.env['stock.location'].search([('usage', '=', 'internal'), ('name', 'ilike', 'kitchen')],
                                                        limit=1)
        warehouse_loc = self.env['stock.location'].search([('usage', '=', 'internal'), ('name', 'ilike', 'warehouse')],
                                                          limit=1)


        for line in self.request_line_ids:
            product = self.env['product.product'].browse(line.product_id)
            bom = self.env['mrp.bom'].search([
                '|',
                ('product_id', '=', product.id),  # Match variant-specific BOM
                ('product_tmpl_id', '=', product.product_tmpl_id.id),  # Fallback to template
                ('company_id', '=', self.env.company.id),  # Match current company
                # ('type', '=', 'normal'),  # Optional: Filter by BOM type
            ], order='sequence, product_id', limit=1)
            if not bom:
                raise UserError(f"No BOM found for {product.display_name}")
            mo = Production.create({
                'product_id': product.id,
                'product_qty': line.quantity,
                'product_uom_id': product.uom_id.id,
                'bom_id': bom.id,
                'location_src_id': warehouse_loc.id,
                'location_dest_id': kitchen_loc.id,
                'origin': f"Kitchen Request {self.id}",
            })

            # confirm and reserve components
            mo.action_confirm()
            # mo.action_assign()


    def action_issue_to_warehouse(self):
        """Send this daily request’s lines into warehouse.kitchen.request"""
        self.ensure_one()
        WarehouseReq = self.env['warehouse.kitchen.request']

        kitchen_location = self.env['stock.location'].search([('usage', '=', 'internal'), ('name', 'ilike', 'Kitchen')], limit=1)
        warehouse_location = self.env['stock.location'].search([('usage', '=', 'internal'), ('name', 'ilike', 'warehouse')], limit=1)

        product_uom = []

        if not kitchen_location or not warehouse_location:
            raise UserError("Please configure both a Warehouse and a Kitchen internal stock location.")

        for line in self.request_line_ids:

            product_uom = self.env['product.product'].browse(line.product_id).uom_id
            if not product_uom:
                continue

        # Create the header in warehouse.kitchen.request
        wh_req = WarehouseReq.create({
            'date': self.date,
            'res_id': self.id,
            'warehouse_id': warehouse_location.id,  # or a field on daily_request
            'kitchen_request_id': self.id,
            'line_ids': [
                (0, 0, {
                    'product_id': line.product_id,
                    'quantity': line.quantity,
                    'uom_id': product_uom.id,
                    'dest_location_id': kitchen_location.id,
                })
                for line in self.request_line_ids
            ],
        })

        self.state = 'request'

        wh_req.action_send()  # if you want to immediately move state to 'sent' and trigger transfers
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'warehouse.kitchen.request',
            'res_id': wh_req.id,
            'view_mode': 'form',
            'target': 'current',
        }

class KitchenDailyRequestLine(models.Model):
    _name = 'kitchen.daily.request.line'
    _description = 'Kitchen Daily Request Line'

    daily_request_id = fields.Many2one('kitchen.daily.request', ondelete='cascade')
    product_id = fields.Integer(string='Product ID', required=True)
    quantity = fields.Float(string='Quantity', required=True)
    menu_name_id = fields.Many2one('kitchen.menu', string='Menu Name')
