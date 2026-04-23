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
        limit_type = "two" if "yes" in product_name else "one"

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
                "day_id": rec.day_id.id if rec.day_id else None,

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
        # 🔥 APPLY LIMIT PER DAY (FIXED LOGIC)
        # ==================================================
        for city in city_map:
            for location in city_map[city]:

                slots = city_map[city][location]

                # -----------------------------
                # GROUP BY DAY
                # -----------------------------
                day_map = {}
                for slot in slots:
                    day_id = slot.get("day_id") or 0
                    day_map.setdefault(day_id, []).append(slot)

                final_slots = []

                # -----------------------------
                # APPLY LIMIT PER DAY
                # -----------------------------
                for day_id, day_slots in day_map.items():

                    # sort by time
                    day_slots.sort(key=lambda x: x.get("start_time") or 0)

                    if not day_slots:
                        continue

                    if limit_type == "two":
                        # ✅ YES → first 2 slots per day
                        final_slots.extend(day_slots[:2])
                    else:
                        # ✅ NO → last 1 slot per day
                        final_slots.append(day_slots[-1])

                # -----------------------------
                # FINAL SORT (OPTIONAL)
                # -----------------------------
                final_slots.sort(key=lambda x: (x.get("day_id") or 0, x.get("start_time") or 0))

                city_map[city][location] = final_slots

        return city_map