from odoo import models, fields, api


class QurbaniDay(models.Model):
    _name = 'qurbani.day'
    _description = 'Qurbani Day'


    name = fields.Char('Day')
    web_qurbani_day = fields.Char('Web Qurbani Day')

    date = fields.Date('Date')


    @api.model
    def validate_qurbani_day(self, day_name):
        day = self.search([('web_qurbani_day', '=', day_name)], limit=1)

        if not day:
            return {
                'valid': False,
                'message': 'Selected Qurbani day not found.'
            }

        if day.date and day.date < fields.Date.today():
            return {
                'valid': False,
                'message': 'Selected Qurbani day has already passed.'
            }

        return {
            'valid': True
        }