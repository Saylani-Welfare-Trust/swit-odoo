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

        Demand = self.env['qurbani.demand']
        Distribution = self.env['distribution.schedule']

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
        # PREVENT DUPLICATE GENERATION
        # -----------------------------
        existing = Demand.search([
            ('hijri_id', '=', self.hijri_id.id),
            ('day_id', '=', self.day_id.id),
            ('slaughter_location_id', '=', self.slaughter_location_id.id)
        ], limit=1)

        if existing:
            raise UserError("Demand already generated for this combination.")

        # -----------------------------
        # CREATE DEMAND
        # -----------------------------
        for record in distribution_schedule:

            # ✅ Validate POS products
            if not record.pos_product_ids:
                raise UserError(
                    f"No POS products found for distribution slot at {record.start_time}."
                )

            # ✅ Validate slaughter link
            if not record.slaughter_schedule_id:
                raise UserError(
                    f"Slaughter slot not linked for distribution at {record.start_time}. "
                    f"Please regenerate schedule properly."
                )

            slaughter = record.slaughter_schedule_id

            for pos_product in record.pos_product_ids:

                # -----------------------------
                # PREVENT DUPLICATE PER SLOT
                # -----------------------------
                existing_line = Demand.search([
                    ('hijri_id', '=', record.hijri_id.id),
                    ('day_id', '=', record.day_id.id),
                    ('slaughter_location_id', '=', record.slaughter_location_id.id),
                    ('distribution_location_id', '=', record.location_id.id),
                    ('distribution_start_time', '=', record.start_time),
                    ('pos_product_id', '=', pos_product.id),
                ], limit=1)

                if existing_line:
                    continue  # skip duplicates safely

                # -----------------------------
                # CREATE RECORD
                # -----------------------------
                Demand.create({
                    'hijri_id': record.hijri_id.id,
                    'day_id': record.day_id.id,

                    # City
                    'city_location_id': slaughter.city_location_id.id if hasattr(slaughter, 'city_location_id') else False,

                    'city_demand': 0,

                    # Slaughter
                    'slaughter_location_id': record.slaughter_location_id.id,
                    'slaughter_start_time': slaughter.start_time,
                    'slaughter_end_time': slaughter.end_time,

                    # Distribution
                    'distribution_location_id': record.location_id.id,
                    'distribution_start_time': record.start_time,
                    'distribution_end_time': record.end_time,

                    # Products
                    'inventory_product_id': record.inventory_product_id.id,
                    'pos_product_id': pos_product.id,
                })