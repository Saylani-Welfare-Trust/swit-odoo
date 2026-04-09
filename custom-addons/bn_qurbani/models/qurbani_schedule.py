from odoo import models, fields, api


class QurbaniSchedule(models.Model):
    _name = 'qurbani.schedule'
    _description = 'Qurbani Schedule'

    day_id = fields.Many2one('qurbani.day', string="Day", required=True)

    start_time = fields.Float(string="Start Time")
    end_time = fields.Float(string="End Time")

    livestock_product_id = fields.Many2one(
        'product.product',
        string="Livestock Product",
        domain="[('type', '=', 'product'), ('is_livestock', '=', True)]",
    )

    service_product_id = fields.Many2one(
        'product.product',
        string="Service Product",
        domain="[('type', '=', 'service'), ('is_livestock', '=', True)]",
    )

    location_id = fields.Many2one(
        'stock.location',
        string="Location",
    )

    qty_available = fields.Float(
        related='livestock_product_id.qty_available',
        string="On Hand Quantity",
        readonly=True
    )

    total_hissa = fields.Integer(
        string="Total Hissa",
        store=True,
        compute="_compute_total_hissa"
    )

    current_hissa = fields.Integer(
        string="Current Hissa",
        default=0
    )

    option = fields.Selection(
        [('yes', 'Yes'), ('no', 'No')],
        default="yes",
        string="Option"
    )

    @api.depends('livestock_product_id', 'qty_available')
    def _compute_total_hissa(self):
        for record in self:
            hissa_per_unit = 0

            if record.livestock_product_id:
                product_name = record.livestock_product_id.name.lower()

                if 'cow' in product_name:
                    hissa_per_unit = 7
                elif 'goat' in product_name:
                    hissa_per_unit = 1

            record.total_hissa = hissa_per_unit * record.qty_available

    # =========================
    # DELIVERY CREATION LOGIC
    # =========================
    def action_update_inventory(self):
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']

        # ✅ Get Customer Location
        customer_location = self.env.ref('stock.stock_location_customers')

        for record in self:
            if not record.livestock_product_id or not record.location_id:
                continue

            product = record.livestock_product_id
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
                'origin': record.day_id.name or 'Qurbani Schedule',
            })

            # -------------------------
            # Create Move
            # -------------------------
            move = StockMove.create({
                'name': product.name,
                'product_id': product.id,
                'product_uom_qty': qty,
                'quantity': product.uom_id.id,
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
                move_line.qty_done = qty

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