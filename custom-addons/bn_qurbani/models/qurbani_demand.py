from odoo import models, fields, api
from odoo.exceptions import UserError


class QurbaniDemand(models.Model):
    _name = 'qurbani.demand'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = 'Qurbani Demand'

    # --------------------------------
    # BASIC FIELDS
    # --------------------------------
    hijri_id = fields.Many2one('hijri', string="Hijri", tracking=True)
    day_id = fields.Many2one('qurbani.day', string="Day", tracking=True)
    city_location_id = fields.Many2one('stock.location', string='City', tracking=True)

    city_demand = fields.Float('City Demand', tracking=True)
    total_city_demand = fields.Float(compute="_compute_total_city_demand", store=True)
    remaining_city_demand = fields.Float(compute="_compute_remaining_city_demand", store=True)

    slaughter_location_id = fields.Many2one('stock.location', string='Slaughter Location', tracking=True)
    slaughter_start_time = fields.Float('Slaughter Start Time')
    slaughter_end_time = fields.Float('Slaughter End Time')

    distribution_location_id = fields.Many2one('stock.location', string='Distribution Location', tracking=True)
    distribution_start_time = fields.Float('Distribution Start Time')
    distribution_end_time = fields.Float('Distribution End Time')

    inventory_product_id = fields.Many2one('product.product', string='Inventory Product', tracking=True)
    pos_product_id = fields.Many2one('product.product', string='POS Product', tracking=True)

    inventory_on_hand = fields.Float(related='inventory_product_id.qty_available', string="Inventory On Hand")
    pos_on_hand = fields.Float(related='pos_product_id.qty_available', string="POS On Hand")

    # --------------------------------
    # CITY DEMAND COMPUTE
    # --------------------------------
    @api.depends('city_demand')
    def _compute_total_city_demand(self):
        for record in self:
            record.total_city_demand = record.city_demand

    @api.depends('city_demand')
    def _compute_remaining_city_demand(self):
        for record in self:
            record.remaining_city_demand = record.city_demand

    # --------------------------------
    # HISSA LOGIC
    # --------------------------------
    total_hissa = fields.Integer(compute="_compute_total_hissa", store=True)
    booked_hissa = fields.Integer(default=0)
    current_hissa = fields.Integer(default=0)
    remaining_hissa = fields.Integer(compute="_compute_remaining_hissa", store=True)

    @api.depends('total_hissa', 'booked_hissa')
    def _compute_remaining_hissa(self):
        for record in self:
            record.remaining_hissa = record.total_hissa - record.booked_hissa

    @api.depends('city_demand', 'inventory_product_id')
    def _compute_total_hissa(self):
        for record in self:
            hissa_per_unit = 0

            if record.inventory_product_id:
                name = record.inventory_product_id.name.lower()

                if 'cow' in name:
                    hissa_per_unit = 7
                elif 'goat' in name:
                    hissa_per_unit = 1

            record.total_hissa = int(hissa_per_unit * record.city_demand)

    # --------------------------------
    # INVENTORY UPDATE
    # --------------------------------
    def action_update_inventory(self):
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']

        customer_location = self.env.ref('stock.stock_location_customers')

        for record in self:

            # ✅ VALIDATION
            if not record.inventory_product_id:
                raise UserError("Inventory product is required.")

            if not record.distribution_location_id:
                raise UserError("Distribution location is required.")

            product = record.inventory_product_id
            name = product.name.lower()
            current_hissa = record.current_hissa or 0

            # Determine quantity
            if 'cow' in name:
                divisor = 7
                qty = int(current_hissa // 7)
            elif 'goat' in name:
                divisor = 1
                qty = int(current_hissa)
            else:
                raise UserError("Unsupported product type.")

            if qty <= 0:
                raise UserError("No quantity available to deliver.")

            picking_type = self.env['stock.picking.type'].search(
                [('code', '=', 'outgoing')], limit=1
            )

            if not picking_type:
                raise UserError("No outgoing picking type found!")

            # Create picking
            picking = StockPicking.create({
                'picking_type_id': picking_type.id,
                'location_id': record.distribution_location_id.id,
                'location_dest_id': customer_location.id,
                'origin': record.day_id.name or 'Qurbani Demand',
            })

            # Create move
            StockMove.create({
                'name': product.name,
                'product_id': product.id,
                'product_uom_qty': qty,
                'product_uom': product.uom_id.id,
                'picking_id': picking.id,
                'location_id': record.distribution_location_id.id,
                'location_dest_id': customer_location.id,
            })

            picking.action_confirm()
            picking.action_assign()

            for move_line in picking.move_line_ids:
                move_line.quantity = qty

            picking.button_validate()

            # Update hissa
            used_hissa = qty * divisor
            record.current_hissa = max(current_hissa - used_hissa, 0)

    # --------------------------------
    # DISTRIBUTION DETAILS API
    # --------------------------------
    @api.model
    def get_distribution_details(self, product_id):

        last_hijri = self.env['hijri'].search([], order="id desc", limit=1)
        if not last_hijri:
            return {}

        records = self.search([
            ('hijri_id', '=', last_hijri.id),
            ('pos_product_id', '=', product_id)
        ])

        city_map = {}

        for rec in records:

            city = rec.city_location_id.name.split('/')[-1] if rec.city_location_id else "Unknown City"
            location = rec.distribution_location_id.name.split('/')[-1] if rec.distribution_location_id else "Unknown Location"

            city_map.setdefault(city, {})
            city_map[city].setdefault(location, [])

            city_map[city][location].append({
                "id": rec.id,
                "day": rec.day_id.name if rec.day_id else "",
                "product": rec.pos_product_id.name if rec.pos_product_id else "",

                # ✅ SLAUGHTER DETAILS
                "slaughter_location_id": rec.slaughter_location_id.id if rec.slaughter_location_id else None,
                "slaughter_start_time": rec.slaughter_start_time,
                "slaughter_end_time": rec.slaughter_end_time,

                # ✅ DISTRIBUTION DETAILS
                "distribution_location_id": rec.distribution_location_id.id if rec.distribution_location_id else None,
                "distribution_start_time": rec.distribution_start_time,
                "distribution_end_time": rec.distribution_end_time,

                # ✅ SLOT INFO
                "start_time": rec.distribution_start_time,
                "end_time": rec.distribution_end_time,
                "remaining_hissa": rec.remaining_hissa,
            })

        return city_map