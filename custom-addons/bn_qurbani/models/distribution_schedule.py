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

        # Fetch all relevant records in one go, with prefetched related fields
        records = self.search([
            ('hijri_id', '=', last_hijri.id),
            ('pos_product_ids', 'in', product_id)
        ])

        if not records:
            return {}

        # Prefetch all related objects to avoid repeated SQL
        records.fetch(['slaughter_schedule_id', 'location_id', 'day_id', 'inventory_product_id',
                    'slaughter_location_id', 'start_time', 'end_time'])
        records.slaughter_schedule_id.fetch(['start_time', 'end_time', 'city_location_id'])
        records.location_id.fetch(['name'])
        records.day_id.fetch(['name'])
        records.inventory_product_id.fetch(['name'])
        records.slaughter_location_id.fetch(['name'])

        # Prepare a map of (day_id, hijri_id, slaughter_location_id, inventory_product_id, start_time, end_time) -> slot demand
        slot_demand_map = {}
        # Collect unique keys for slot demands
        slot_demand_keys = set()
        for rec in records:
            slaughter = rec.slaughter_schedule_id
            if not slaughter:
                continue
            # Use tuple as key
            key = (rec.day_id.id if rec.day_id else 0,
                rec.hijri_id.id,
                rec.slaughter_location_id.id if rec.slaughter_location_id else 0,
                rec.inventory_product_id.id if rec.inventory_product_id else 0,
                slaughter.start_time,
                slaughter.end_time)
            slot_demand_keys.add(key)

        if slot_demand_keys:
            # Build domain for slot demands
            domain = ['|', ('day_id', '=', 0), '&']
            # We'll use OR for each key? Better to use a more efficient approach: fetch all for the hijri and then filter in Python
            # Since keys are derived from fields, we can fetch all slot demands for this hijri and then match in Python
            slot_demands = self.env['qurbani.slaughter.slot.demand'].search([
                ('hijri_id', '=', last_hijri.id)
            ])
            # Prefetch fields used in matching
            slot_demands.fetch(['day_id', 'hijri_id', 'slaughter_location_id', 'inventory_product_id', 'start_time', 'end_time', 'remaining_hissa'])
            for sd in slot_demands:
                key = (sd.day_id.id if sd.day_id else 0,
                    sd.hijri_id.id,
                    sd.slaughter_location_id.id if sd.slaughter_location_id else 0,
                    sd.inventory_product_id.id if sd.inventory_product_id else 0,
                    sd.start_time,
                    sd.end_time)
                slot_demand_map[key] = sd

        city_map = {}
        for rec in records:
            # City name
            city = "Unknown City"
            if rec.slaughter_schedule_id and rec.slaughter_schedule_id.city_location_id:
                city = rec.slaughter_schedule_id.city_location_id.name.split('/')[-1]

            location = rec.location_id.name.split('/')[-1] if rec.location_id else "Unknown Location"

            slaughter = rec.slaughter_schedule_id
            slaughter_start = slaughter.start_time if slaughter else False
            slaughter_end = slaughter.end_time if slaughter else False
            slaughter_location_id = rec.slaughter_location_id.id if rec.slaughter_location_id else False

            # Get remaining hissa from map
            remaining = 0
            slot_demand_id = False
            if slaughter:
                key = (rec.day_id.id if rec.day_id else 0,
                    rec.hijri_id.id,
                    rec.slaughter_location_id.id if rec.slaughter_location_id else 0,
                    rec.inventory_product_id.id if rec.inventory_product_id else 0,
                    slaughter_start,
                    slaughter_end)
                slot_demand = slot_demand_map.get(key)
                if slot_demand:
                    remaining = slot_demand.remaining_hissa
                    slot_demand_id = slot_demand.id

            if remaining <= 0:
                continue

            slot = {
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
                "slot_demand_id": slot_demand_id,
            }

            city_map.setdefault(city, {}).setdefault(location, []).append(slot)

        # Apply limit per day (same logic as original)
        for city in city_map:
            for location in city_map[city]:
                slots = city_map[city][location]
                day_map = {}
                for slot in slots:
                    day_id = slot.get("day_id") or 0
                    day_map.setdefault(day_id, []).append(slot)

                final_slots = []
                for day_id, day_slots in day_map.items():
                    day_slots.sort(key=lambda x: x.get("start_time") or 0)
                    if not day_slots:
                        continue
                    if limit_type == "two":
                        final_slots.extend(day_slots[:2])
                    else:
                        final_slots.append(day_slots[-1])

                final_slots.sort(key=lambda x: (x.get("day_id") or 0, x.get("start_time") or 0))
                city_map[city][location] = final_slots

        return city_map