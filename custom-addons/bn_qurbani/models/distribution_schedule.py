from odoo import models, fields, api


class DistributionSchedule(models.Model):
    _name = 'distribution.schedule'
    _description = 'Distribution Schedule'


    start_time = fields.Float('Start Time', tracking=True)
    end_time = fields.Float('End Time', tracking=True)

    day_id = fields.Many2one('qurbani.day', string="Day", tracking=True)
    hijri_id = fields.Many2one('hijri', string="Hijri", tracking=True)
    inventory_product_id = fields.Many2one(
        'product.product',
        string="Inventory Product",
        tracking=True
    )
    pos_product_id = fields.Many2one(
        'product.product',
        string="POS Product",
        tracking=True
    )
    slaughter_schedule_id = fields.Many2one('slaughter.schedule', string="Slaughter Schedule", tracking=True)

    demand = fields.Integer(related='slaughter_schedule_id.demand', string="Demand", store=True, tracking=True)

    distribution_location_ids = fields.Many2many('stock.location', string="Distribution Locations", compute="_set_distribution_location_ids", tracking=True)

    location_id = fields.Many2one('stock.location', string="Distribution Location", tracking=True)

    total_hissa = fields.Integer(
        string="Total Hissa",
        store=True,
        compute="_compute_total_hissa"
    )
    booked_hissa = fields.Integer(
        string="Booked Hissa",
        default=0
    )
    current_hissa = fields.Integer(
        string="Current Hissa",
        default=0
    )
    remaining_hissa = fields.Integer(
        string="Remaining Hissa",
        compute="_compute_remaining_hissa",
        store=True,
        default=0
    )


    @api.depends('total_hissa', 'booked_hissa')
    def _compute_remaining_hissa(self):
        for record in self:
            record.remaining_hissa = record.total_hissa - record.booked_hissa

    @api.depends('inventory_product_id', 'slaughter_schedule_id')
    def _compute_total_hissa(self):
        for record in self:
            hissa_per_unit = 0

            if record.inventory_product_id:
                product_name = record.inventory_product_id.name.lower()

                if 'cow' in product_name:
                    hissa_per_unit = 7
                elif 'goat' in product_name:
                    hissa_per_unit = 1

            record.total_hissa = hissa_per_unit * record.demand

    @api.depends('slaughter_schedule_id', 'slaughter_schedule_id.location_ids')
    def _set_distribution_location_ids(self):
        for record in self:
            if record.slaughter_schedule_id:
                record.distribution_location_ids = record.slaughter_schedule_id.location_ids
            else:
                record.distribution_location_ids = False

    # =========================
    # DELIVERY CREATION LOGIC
    # =========================
    def action_update_inventory(self):
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']

        # ✅ Get Customer Location
        customer_location = self.env.ref('stock.stock_location_customers')

        for record in self:
            if not record.inventory_product_id or not record.location_id:
                continue

            product = record.inventory_product_id
            product_name = product.name.lower()
            current_hissa = record.current_hissa or 0

            # -------------------------
            # Determine divisor & qty
            # -------------------------
            if 'cow' in product_name:
                divisor = 7
                qty = int(current_hissa // 7)
            elif 'goat' in product_name:
                divisor = 1
                qty = int(current_hissa)
            else:
                continue

            if qty <= 0:
                continue

            # -------------------------
            # Get Picking Type
            # -------------------------
            picking_type = self.env['stock.picking.type'].search(
                [('code', '=', 'outgoing')],
                limit=1
            )

            if not picking_type:
                raise ValueError("No outgoing picking type found!")

            # -------------------------
            # Create Picking
            # -------------------------
            picking = StockPicking.create({
                'picking_type_id': picking_type.id,
                'location_id': record.location_id.id,
                'location_dest_id': customer_location.id,
                'origin': record.day_id.name or 'Distribution Schedule',
            })

            # -------------------------
            # Create Move
            # -------------------------
            StockMove.create({
                'name': product.name,
                'product_id': product.id,
                'product_uom_qty': qty,
                'product_uom': product.uom_id.id,
                'picking_id': picking.id,
                'location_id': record.location_id.id,
                'location_dest_id': customer_location.id,
            })

            # -------------------------
            # Confirm & Assign
            # -------------------------
            picking.action_confirm()
            picking.action_assign()

            # -------------------------
            # Set Done Quantity
            # -------------------------
            for move_line in picking.move_line_ids:
                move_line.quantity = qty

            # -------------------------
            # Validate Delivery
            # -------------------------
            picking.button_validate()

            # -------------------------
            # 🔥 UPDATE CURRENT HISSA
            # -------------------------
            used_hissa = qty * divisor
            remaining_hissa = current_hissa - used_hissa

            # Safety (never go negative)
            record.current_hissa = max(remaining_hissa, 0)

    @api.model
    def get_distribution_details(self):

        last_hijri = self.env['hijri'].search([], order="id desc", limit=1)
        if not last_hijri:
            return {}

        distributions = self.search([
            ('hijri_id', '=', last_hijri.id)
        ])

        city_map = {}

        for dist in distributions:

            city = dist.slaughter_schedule_id.city_schedule_id.location_id.name or "Unknown City"
            location = dist.location_id.name or "Unknown Location"

            city_map.setdefault(city, {})
            city_map[city].setdefault(location, [])

            city_map[city][location].append({
                "id": dist.id,
                "day": dist.day_id.name if hasattr(dist, "day_id") else "",
                "start_time": dist.start_time,
                "end_time": dist.end_time,
                "remaining_hissa": dist.remaining_hissa,
            })

        return city_map