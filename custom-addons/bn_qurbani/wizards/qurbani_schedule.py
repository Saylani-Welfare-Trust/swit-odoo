from odoo import models, fields


class QurbaniSchedule(models.TransientModel):
    _name = 'qurbani.schedule'
    _description = 'Qurbani Schedule'


    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')

    slot_interval = fields.Float('Slot Interval (in hours)', default=1)
    interval = fields.Float('Slaughter and Distribution Interval (in hours)', default=2)

    hijri_id = fields.Many2one('hijri', string="Hijri Date")
    day_id = fields.Many2one('qurbani.day', string="Qurbani Day")
    

    def action_generate_schedule(self):
        Slaughter = self.env['slaughter.schedule']
        Distribution = self.env['distribution.schedule']

        start = self.start_time
        end = self.end_time

        slot_duration = self.slot_interval or 1
        dist_window = self.interval or 2

        # -----------------------------
        # REMOVE OLD RECORDS
        # -----------------------------
        Slaughter.search([
            ('day_id', '=', self.day_id.id),
            ('hijri_id', '=', self.hijri_id.id)
        ]).unlink()

        Distribution.search([
            ('day_id', '=', self.day_id.id),
            ('hijri_id', '=', self.hijri_id.id)
        ]).unlink()

        # -----------------------------
        # SLAUGHTER SLOTS
        # -----------------------------
        current_time = start
        slaughter_slots = 0  # count slots

        while current_time + slot_duration <= end:
            Slaughter.create({
                'start_time': current_time,
                'end_time': current_time + slot_duration,
                'day_id': self.day_id.id,
                'hijri_id': self.hijri_id.id,
            })

            current_time += slot_duration
            slaughter_slots += 1

        # -----------------------------
        # DISTRIBUTION SLOTS
        # -----------------------------
        # First slaughter slot end
        first_slot_end = start + slot_duration

        # Start after interval jump
        dist_start = first_slot_end + dist_window

        current_time = dist_start

        # Create SAME number of slots as slaughter
        for i in range(slaughter_slots):
            Distribution.create({
                'start_time': current_time,
                'end_time': current_time + slot_duration,
                'day_id': self.day_id.id,
                'hijri_id': self.hijri_id.id,
            })

            current_time += slot_duration