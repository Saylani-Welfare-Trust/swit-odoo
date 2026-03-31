from odoo import models, fields
from odoo.exceptions import ValidationError


type_selection = [
    ('ration', 'Ration'),
    ('distribution', 'Distribution'),
]

state_selection = [
    ('draft', 'Draft'),
    ('issued', 'Issued'),
]


class DailyPlanning(models.Model):
    _name = 'daily.planning'
    _description = 'Daily Planning'
    _inherit = ["mail.thread", "mail.activity.mixin"]


    date = fields.Date(string='Date')

    type = fields.Selection(selection=type_selection, string='Type')

    partner_id = fields.Many2one('res.partner', string='Partner')

    picking_id = fields.Many2one('stock.picking', string='Picking')

    state = fields.Selection(selection=state_selection, string='State', default='draft')


    daily_planning_line_ids = fields.One2many('daily.planning.line', 'daily_planning_id', string='Daily Planning Lines')


    def action_send_issuance(self):
        StockPicking = self.env['stock.picking']

        # ✅ Source = Main Stock
        source_loc = self.env.ref('stock.stock_location_stock')

        # ✅ Destination = Distribution (your custom location)
        dest_loc = self.env['stock.location'].search([
            ('name', 'ilike', 'Distribution'),
            ('usage', '=', 'internal'),
        ], limit=1)

        if not dest_loc:
            raise ValidationError(
                "Distribution location not found. Please create it in Inventory."
            )

        picking_type = self.env.ref('stock.picking_type_internal')

        for rec in self:
            picking = StockPicking.create({
                'picking_type_id': picking_type.id,
                'location_id': source_loc.id,
                'location_dest_id': dest_loc.id,
                'scheduled_date': rec.date,
            })

            move_vals = []
            for line in rec.daily_planning_line_ids:
                product = line.product_id

                if not product:
                    continue

                move_vals.append((0, 0, {
                    'name': product.display_name,
                    'product_id': product.id,
                    'product_uom_qty': 1.0,
                    'product_uom': product.uom_id.id,
                    'location_id': source_loc.id,
                    'location_dest_id': dest_loc.id,
                }))

            if not move_vals:
                picking.unlink()
                raise ValidationError(
                    f"No products found on Daily Planning {rec.id}"
                )

            picking.write({'move_ids_without_package': move_vals})
            picking.action_confirm()
            picking.action_assign()

            if picking.state == 'assigned':
                picking.button_validate()

            rec.picking_id = picking.id

        self.state = 'issued';

        return True