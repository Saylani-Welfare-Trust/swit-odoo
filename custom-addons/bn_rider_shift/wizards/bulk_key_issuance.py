# -*- coding: utf-8 -*-
from odoo import models


class BulkKeyIssuance(models.TransientModel):
    _inherit = 'bulk.key.issuance'

    def _get_scheduled_riders(self):
        schedule_days = self.env['rider.schedule.day'].search([('date', '=', self.date)])
        return schedule_days.mapped('rider_shift_id.rider_id')

    def _get_scheduled_key_bunches(self):
        schedule_days = self.env['rider.schedule.day'].search([
            ('rider_shift_id.rider_id', '=', self.rider_id.id),
            ('date', '=', self.date),
        ])
        return schedule_days.mapped('key_bunch_id')
