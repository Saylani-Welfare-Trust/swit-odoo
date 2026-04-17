from odoo import models, fields


class QurbaniDay(models.Model):
    _name = 'qurbani.day'
    _description = 'Qurbani Day'


    name = fields.Char('Day')