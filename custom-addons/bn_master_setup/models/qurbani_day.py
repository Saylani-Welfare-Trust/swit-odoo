from odoo import models, fields


class QurbaniDay(models.Model):
    _name = 'qurbani.day'
    _description = 'Day Master'

    name = fields.Char(string="Day Name", required=True)