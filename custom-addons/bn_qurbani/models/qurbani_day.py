from odoo import models, fields, api


class QurbaniDay(models.Model):
    _name = 'qurbani.day'
    _description = 'Qurbani Day'

    name = fields.Char('Day')
    web_qurbani_day = fields.Char('Web Qurbani Day')
    date = fields.Date('Date')

    @api.model
    def validate_qurbani_day(self, day_id):
        day = self.browse(day_id)

        if not day:
            return {
                'valid': False,
                'message': 'Selected Qurbani day not found.'
            }

        if not day.date:
            return {
                'valid': False,
                'message': f"No date configured for {day.name or 'the selected Qurbani day'}."
            }

        today = fields.Date.today()

        if day.date <= today:
            return {
                'valid': False,
                'message': (
                    f"Booking is not allowed for {day.name or 'the selected Qurbani day'}. "
                    f"Today date must be before the Eid day date ({day.date})."
                )
            }

        return {
            'valid': True,
            'message': 'Qurbani booking date is valid.'
        }