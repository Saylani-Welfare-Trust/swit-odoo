from odoo import models, fields, api


class DistributionSchedule(models.Model):
    _name = 'distribution.schedule'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = 'Distribution Schedule'


    start_time = fields.Float('Start Time', tracking=True)
    end_time = fields.Float('End Time', tracking=True)

    day_id = fields.Many2one('qurbani.day', string="Day", tracking=True)
    hijri_id = fields.Many2one('hijri', string="Hijri", tracking=True, domain=[('approved', '=', True)])
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

        # ==================================================
        # 1. GET HIJRI
        # ==================================================
        last_hijri = self.env['hijri'].search([('approved', '=', True)], order="id desc", limit=1)

        if not last_hijri:
            return {}

        # ==================================================
        # 2. GET PRODUCT
        # ==================================================
        product = self.env['product.product'].browse(product_id)

        product_name = (product.name or "").lower()

        # ==================================================
        # 3. LIMIT TYPE
        # ==================================================
        limit_type = "two" if "yes" in product_name else "one"

        # ==================================================
        # 4. FETCH RECORDS
        # ==================================================
        records = self.search([
            ('hijri_id', '=', last_hijri.id),
            ('pos_product_ids', 'in', product_id)
        ])

        if not records:
            return {}

        # ==================================================
        # 5. PRELOAD ALL SLOT DEMANDS
        # ==================================================
        demand_domain = [
            ('hijri_id', '=', last_hijri.id),
            ('inventory_product_id', 'in', records.mapped('inventory_product_id').ids),
            ('slaughter_location_id', 'in', records.mapped('slaughter_location_id').ids),
            ('day_id', 'in', records.mapped('day_id').ids),
        ]

        slot_demands = self.env['qurbani.slaughter.slot.demand'].search(demand_domain)

        # ==================================================
        # 6. CREATE FAST LOOKUP MAP
        # ==================================================
        demand_map = {}

        for demand in slot_demands:

            key = (
                demand.day_id.id,
                demand.hijri_id.id,
                demand.slaughter_location_id.id,
                demand.inventory_product_id.id,
                demand.start_time,
                demand.end_time,
            )

            demand_map[key] = demand

        # ==================================================
        # 7. BUILD RESPONSE
        # ==================================================
        city_map = {}

        for rec in records:

            slaughter = rec.slaughter_schedule_id

            if not slaughter:
                continue

            # ==================================================
            # CITY
            # ==================================================
            city = "Unknown City"

            if slaughter.city_location_id and slaughter.city_location_id.name:
                city = slaughter.city_location_id.name.strip()

            # ==================================================
            # LOCATION
            # ==================================================
            location = (
                rec.location_id.name.strip()
                if rec.location_id and rec.location_id.name
                else "Unknown Location"
            )

            city_map.setdefault(city, {})
            city_map[city].setdefault(location, [])

            # ==================================================
            # SLAUGHTER DATA
            # ==================================================
            slaughter_start = slaughter.start_time
            slaughter_end = slaughter.end_time

            slaughter_location_id = (
                rec.slaughter_location_id.id
                if rec.slaughter_location_id
                else False
            )

            # ==================================================
            # GET SLOT DEMAND FROM CACHE
            # ==================================================
            demand_key = (
                rec.day_id.id,
                rec.hijri_id.id,
                rec.slaughter_location_id.id,
                rec.inventory_product_id.id,
                slaughter_start,
                slaughter_end,
            )

            slot_demand = demand_map.get(demand_key)

            remaining = 0
            slot_demand_id = False

            if slot_demand:
                remaining = slot_demand.remaining_hissa
                slot_demand_id = slot_demand.id

            # ==================================================
            # SKIP EMPTY
            # ==================================================
            if remaining <= 0:
                continue

            # ==================================================
            # APPEND SLOT
            # ==================================================
            city_map[city][location].append({
                "id": rec.id,

                "day": rec.day_id.name if rec.day_id else "",
                "day_id": rec.day_id.id if rec.day_id else None,

                "product": (
                    rec.inventory_product_id.name
                    if rec.inventory_product_id
                    else ""
                ),

                "slaughter_location_id": slaughter_location_id,

                "slaughter_start_time": slaughter_start,
                "slaughter_end_time": slaughter_end,

                "distribution_location_id": (
                    rec.location_id.id
                    if rec.location_id
                    else None
                ),

                "distribution_start_time": rec.start_time,
                "distribution_end_time": rec.end_time,

                "start_time": rec.start_time,
                "end_time": rec.end_time,

                "remaining_hissa": remaining,
                "slot_demand_id": slot_demand_id,
            })

        # ==================================================
        # 8. APPLY LIMIT PER DAY
        # ==================================================
        for city, locations in city_map.items():

            for location, slots in locations.items():

                # ==================================================
                # GROUP BY DAY
                # ==================================================
                day_map = {}

                for slot in slots:

                    day_id = slot.get("day_id")

                    if not day_id:
                        continue

                    day_map.setdefault(day_id, [])
                    day_map[day_id].append(slot)

                final_slots = []

                # ==================================================
                # APPLY LIMIT
                # ==================================================
                for day_id, day_slots in day_map.items():

                    # ==================================================
                    # VALID SLOTS ONLY
                    # ==================================================
                    valid_slots = [
                        s for s in day_slots
                        if (s.get("remaining_hissa") or 0) > 0
                    ]

                    if not valid_slots:
                        continue

                    # ==================================================
                    # SORT BY TIME
                    # ==================================================
                    valid_slots = sorted(
                        valid_slots,
                        key=lambda x: x.get("start_time") or 0
                    )

                    # ==================================================
                    # APPLY LIMIT
                    # ==================================================
                    if limit_type == "two":
                        # FIRST 2
                        final_slots.extend(valid_slots[:2])
                    else:
                        # LAST 1
                        final_slots.append(valid_slots[-1])

                # ==================================================
                # FINAL SORT
                # ==================================================
                final_slots = sorted(
                    final_slots,
                    key=lambda x: (
                        x.get("day_id") or 0,
                        x.get("start_time") or 0
                    )
                )

                city_map[city][location] = final_slots

        return city_map
