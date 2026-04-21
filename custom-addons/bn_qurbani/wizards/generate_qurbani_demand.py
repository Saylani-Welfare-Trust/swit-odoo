from odoo import models, fields
from odoo.exceptions import UserError


class GenerateQurbaniDemand(models.TransientModel):
    _name = 'generate.qurbani.demand'
    _description = 'Generate Qurbani Demand'


    hijri_id = fields.Many2one('hijri', string="Hijri")
    day_id = fields.Many2one('qurbani.day', string="Day")

    slaughter_location_id = fields.Many2one('stock.location', string='Slaughter Location')


    def action_generate_demand(self):
        self.ensure_one()

        CityDemand = self.env['qurbani.city.demand']
        SlaughterDemand = self.env['qurbani.slaughter.demand']
        SlaughterSlotDemand = self.env['qurbani.slaughter.slot.demand']
        Distribution = self.env['distribution.schedule']

        new_record = {}

        # -----------------------------
        # BASIC VALIDATIONS
        # -----------------------------
        if not self.hijri_id or not self.day_id:
            raise UserError("Please select Hijri Date and Day.")

        if not self.slaughter_location_id:
            raise UserError("Slaughter location is required.")

        # -----------------------------
        # FETCH DISTRIBUTION RECORDS
        # -----------------------------
        distribution_schedule = Distribution.search([
            ('hijri_id', '=', self.hijri_id.id),
            ('day_id', '=', self.day_id.id),
            ('slaughter_location_id', '=', self.slaughter_location_id.id)
        ])

        if not distribution_schedule:
            raise UserError("No distribution schedule found for selected criteria.")

        # -----------------------------
        # PREVENT DUPLICATE GENERATION (GLOBAL)
        # -----------------------------
        existing = SlaughterDemand.search([
            ('hijri_id', '=', self.hijri_id.id),
            ('day_id', '=', self.day_id.id),
            ('slaughter_location_id', '=', self.slaughter_location_id.id)
        ], limit=1)

        if existing:
            raise UserError("Demand already generated for this combination.")

        # -----------------------------
        # BUILD DATA (CITY → PRODUCT → SLOTS)
        # -----------------------------
        for record in distribution_schedule:

            # Validate POS products
            if not record.pos_product_ids:
                raise UserError(
                    f"No POS products found for distribution slot at {record.start_time}."
                )

            # Validate slaughter link
            if not record.slaughter_schedule_id:
                raise UserError(
                    f"Slaughter slot not linked for distribution at {record.start_time}."
                )

            slaughter = record.slaughter_schedule_id

            # Validate city
            if not slaughter.city_location_id:
                raise UserError(
                    f"City not defined in slaughter schedule at {record.start_time}."
                )

            city_id = slaughter.city_location_id.id
            product_id = slaughter.inventory_product_id.id

            if not product_id:
                raise UserError(
                    f"Inventory product missing in slaughter schedule at {record.start_time}."
                )

            # -----------------------------
            # INIT CITY
            # -----------------------------
            if city_id not in new_record:
                new_record[city_id] = {}

            # -----------------------------
            # INIT PRODUCT UNDER CITY
            # -----------------------------
            if product_id not in new_record[city_id]:
                new_record[city_id][product_id] = {
                    'slaughter_location_id': record.slaughter_location_id.id,
                    'slots': []
                }

            # -----------------------------
            # ADD SLOT (MULTIPLE ALLOWED)
            # -----------------------------
            slot_vals = {
                'start_time': slaughter.start_time,
                'end_time': slaughter.end_time,
            }

            # Avoid duplicate slots in memory
            if slot_vals not in new_record[city_id][product_id]['slots']:
                new_record[city_id][product_id]['slots'].append(slot_vals)

        # -----------------------------
        # FINAL VALIDATION
        # -----------------------------
        if not new_record:
            raise UserError("No valid data found to generate demand.")

        # -----------------------------
        # CREATE RECORDS
        # -----------------------------
        for city_id, products in new_record.items():

            for product_id, details in products.items():

                # -----------------------------
                # CITY DEMAND
                # -----------------------------
                city_demand = CityDemand.search([
                    ('hijri_id', '=', self.hijri_id.id),
                    ('day_id', '=', self.day_id.id),
                    ('city_location_id', '=', city_id),
                    ('inventory_product_id', '=', product_id),
                ], limit=1)

                if not city_demand:
                    city_demand = CityDemand.create({
                        'hijri_id': self.hijri_id.id,
                        'day_id': self.day_id.id,
                        'city_location_id': city_id,
                        'inventory_product_id': product_id,
                    })

                # -----------------------------
                # SLAUGHTER DEMAND
                # -----------------------------
                slaughter_demand = SlaughterDemand.search([
                    ('hijri_id', '=', self.hijri_id.id),
                    ('day_id', '=', self.day_id.id),
                    ('city_location_id', '=', city_id),
                    ('slaughter_location_id', '=', details['slaughter_location_id']),
                    ('inventory_product_id', '=', product_id),
                ], limit=1)

                if not slaughter_demand:
                    slaughter_demand = SlaughterDemand.create({
                        'hijri_id': self.hijri_id.id,
                        'day_id': self.day_id.id,
                        'city_location_id': city_id,
                        'slaughter_location_id': details['slaughter_location_id'],
                        'inventory_product_id': product_id,
                    })

                # -----------------------------
                # SLOT DEMAND (MULTIPLE)
                # -----------------------------
                for slot in details['slots']:

                    existing_slot = SlaughterSlotDemand.search([
                        ('hijri_id', '=', self.hijri_id.id),
                        ('day_id', '=', self.day_id.id),
                        ('slaughter_location_id', '=', details['slaughter_location_id']),
                        ('inventory_product_id', '=', product_id),
                        ('start_time', '=', slot['start_time']),
                        ('end_time', '=', slot['end_time']),
                    ], limit=1)

                    if existing_slot:
                        continue  # skip duplicates safely

                    SlaughterSlotDemand.create({
                        'hijri_id': self.hijri_id.id,
                        'day_id': self.day_id.id,
                        'slaughter_location_id': details['slaughter_location_id'],
                        'inventory_product_id': product_id,
                        'start_time': slot['start_time'],
                        'end_time': slot['end_time'],
                    })