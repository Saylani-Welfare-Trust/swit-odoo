from odoo import models, fields, api
from odoo.exceptions import UserError


class QurbaniSchedule(models.TransientModel):
    _name = 'qurbani.schedule'
    _description = 'Qurbani Schedule'

    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')

    slot_interval = fields.Float('Slot Interval (in hours)', default=1)
    interval = fields.Float('Slaughter and Distribution Interval (in hours)', default=2)

    city_schedule_id = fields.Many2one('city.schedule', string="City")

    # Related fields
    slaughter_location_id = fields.Many2one(
        related="city_schedule_id.slaughter_location_id",
        string="Slaughter Location",
        store=True,
        readonly=True
    )

    inventory_product_id = fields.Many2one(
        related="city_schedule_id.inventory_product_id",
        string="Inventory Product",
        store=True,
        readonly=True
    )

    hijri_id = fields.Many2one('hijri', string="Hijri Date")
    day_id = fields.Many2one('qurbani.day', string="Qurbani Day")

    # --------------------------------------------------
    # MAIN ACTION
    # --------------------------------------------------
    def action_generate_schedule(self):
        self.ensure_one()

        Slaughter = self.env['slaughter.schedule']
        Distribution = self.env['distribution.schedule']

        start = self.start_time
        end = self.end_time

        slot_duration = self.slot_interval or 1
        dist_window = self.interval or 2

        # -----------------------------
        # VALIDATIONS
        # -----------------------------
        if start >= end:
            raise UserError("End time must be greater than start time.")

        if not self.city_schedule_id:
            raise UserError("Please select a city schedule.")

        if not self.slaughter_location_id:
            raise UserError("Slaughter location is not set in city schedule.")

        if not self.inventory_product_id:
            raise UserError("Inventory product is not set in city schedule.")

        if not self.day_id or not self.hijri_id:
            raise UserError("Please select Hijri Date and Qurbani Day.")

        # -----------------------------
        # REMOVE OLD RECORDS
        # -----------------------------
        Slaughter.search([
            ('day_id', '=', self.day_id.id),
            ('hijri_id', '=', self.hijri_id.id),
            ('location_id', '=', self.slaughter_location_id.id),
            ('inventory_product_id', '=', self.inventory_product_id.id),
        ]).unlink()

        Distribution.search([
            ('day_id', '=', self.day_id.id),
            ('hijri_id', '=', self.hijri_id.id),
            ('slaughter_location_id', '=', self.slaughter_location_id.id),
            ('inventory_product_id', '=', self.inventory_product_id.id),
        ]).unlink()

        # -----------------------------
        # GENERATE SLAUGHTER SLOTS
        # -----------------------------
        slaughter_slots = self._generate_slaughter_slots(
            Slaughter, start, end, slot_duration
        )

        # -----------------------------
        # GENERATE DISTRIBUTION SLOTS
        # -----------------------------
        self._generate_distribution_slots(
            Distribution, start, slot_duration, dist_window, slaughter_slots
        )

    # --------------------------------------------------
    # SLAUGHTER SLOT GENERATION
    # --------------------------------------------------
    def _generate_slaughter_slots(self, Slaughter, start, end, slot_duration):
        current_time = start
        slaughter_slots = 0

        while current_time + slot_duration <= end:
            Slaughter.create({
                'start_time': current_time,
                'end_time': current_time + slot_duration,
                'day_id': self.day_id.id,
                'hijri_id': self.hijri_id.id,
                'city_location_id': self.city_schedule_id.location_id.id,
                'location_id': self.slaughter_location_id.id,
                'inventory_product_id': self.inventory_product_id.id,
            })

            current_time += slot_duration
            slaughter_slots += 1

        return slaughter_slots

    # --------------------------------------------------
    # DISTRIBUTION SLOT GENERATION
    # --------------------------------------------------
    def _generate_distribution_slots(
        self, Distribution, start, slot_duration, dist_window, slaughter_slots
    ):
        first_slot_end = start + slot_duration
        current_time = first_slot_end + dist_window

        for i in range(slaughter_slots):
            for distribution in self.city_schedule_id.distribution_location_ids:
                Distribution.create({
                    'start_time': current_time,
                    'end_time': current_time + slot_duration,
                    'day_id': self.day_id.id,
                    'hijri_id': self.hijri_id.id,
                    'slaughter_location_id': self.slaughter_location_id.id,
                    'location_id': distribution.id,
                    'inventory_product_id': self.inventory_product_id.id,
                    'interval': self.interval or 2,
                    'slot_interval': self.slot_interval or 1,
                })

            current_time += slot_duration