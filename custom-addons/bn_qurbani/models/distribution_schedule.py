from odoo import models, fields, api


class DistributionSchedule(models.Model):
    _name = 'distribution.schedule'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = 'Distribution Schedule'


    start_time = fields.Float('Start Time', tracking=True)
    end_time = fields.Float('End Time', tracking=True)

    day_id = fields.Many2one('qurbani.day', string="Day", tracking=True)
    hijri_id = fields.Many2one('hijri', string="Hijri", tracking=True)
    inventory_product_id = fields.Many2one('product.product', string="Inventory Product", tracking=True)
    slaughter_location_id = fields.Many2one('stock.location', string="Slaughter Location", tracking=True)

    location_id = fields.Many2one('stock.location', string="Distribution Location", tracking=True)

    inventory_product_name = fields.Char(related='inventory_product_id.name', string="Inentory Product Name")

    pos_product_ids = fields.Many2many('product.product', string="POS Products", tracking=True)

    slot_interval = fields.Float('Slot Interval (in hours)', default=1)
    interval = fields.Float('Slaughter and Distribution Interval (in hours)', default=2)

    slaughter_schedule_id = fields.Many2one('slaughter.schedule', string="Slaughter Schedule", tracking=True)

    # --------------------------------
    # DISTRIBUTION DETAILS API
    # --------------------------------
    @api.model
    def get_distribution_details(self, product_id):

        last_hijri = self.env['hijri'].search([], order="id desc", limit=1)
        if not last_hijri:
            return {}

        # 🔥 GET PRODUCT ONCE
        product = self.env['product.product'].browse(product_id)
        product_name = (product.name or "").lower()

        # 🔥 DECIDE SLOT LIMIT BASED ON PRODUCT
        if "yes" in product_name:
            limit_type = "two"
        else:
            limit_type = "one"

        records = self.search([
            ('hijri_id', '=', last_hijri.id),
            ('pos_product_ids', 'in', product_id)
        ])

        city_map = {}

        for rec in records:

            # -----------------------------
            # CITY
            # -----------------------------
            city = "Unknown City"
            if rec.slaughter_schedule_id and rec.slaughter_schedule_id.city_location_id:
                city = rec.slaughter_schedule_id.city_location_id.name.split('/')[-1]

            # -----------------------------
            # LOCATION
            # -----------------------------
            location = rec.location_id.name.split('/')[-1] if rec.location_id else "Unknown Location"

            city_map.setdefault(city, {})
            city_map[city].setdefault(location, [])

            slaughter = rec.slaughter_schedule_id

            slaughter_start = slaughter.start_time if slaughter else False
            slaughter_end = slaughter.end_time if slaughter else False
            slaughter_location_id = rec.slaughter_location_id.id if rec.slaughter_location_id else False

            # -----------------------------
            # REMAINING HISSA
            # -----------------------------
            remaining = 0
            if slaughter:
                slot_demand = self.env['qurbani.slaughter.slot.demand'].search([
                    ('day_id', '=', rec.day_id.id),
                    ('hijri_id', '=', rec.hijri_id.id),
                    ('slaughter_location_id', '=', rec.slaughter_location_id.id),
                    ('inventory_product_id', '=', rec.inventory_product_id.id),
                    ('start_time', '=', slaughter_start),
                    ('end_time', '=', slaughter_end),
                ], limit=1)

                if slot_demand:
                    remaining = slot_demand.remaining_hissa

            # -----------------------------
            # ONLY KEEP AVAILABLE SLOTS
            # -----------------------------
            if remaining <= 0:
                continue

            # -----------------------------
            # APPEND SLOT
            # -----------------------------
            city_map[city][location].append({
                "id": rec.id,
                "day": rec.day_id.name if rec.day_id else "",
                "product": rec.inventory_product_id.name if rec.inventory_product_id else "",

                "slaughter_location_id": slaughter_location_id,
                "slaughter_start_time": slaughter_start,
                "slaughter_end_time": slaughter_end,

                "distribution_location_id": rec.location_id.id if rec.location_id else None,
                "distribution_start_time": rec.start_time,
                "distribution_end_time": rec.end_time,

                "start_time": rec.start_time,
                "end_time": rec.end_time,

                "remaining_hissa": remaining,
            })

        # ==================================================
        # 🔥 APPLY LIMIT BASED ON PRODUCT
        # ==================================================
        for city in city_map:
            for location in city_map[city]:

                slots = city_map[city][location]

                # sort by time
                slots.sort(key=lambda x: x.get("start_time") or 0)

                if not slots:
                    continue

                if limit_type == "two":
                    # ✅ YES → first 2
                    city_map[city][location] = slots[:2]
                else:
                    # ✅ NO → last 1
                    city_map[city][location] = [slots[-1]]

        return city_map