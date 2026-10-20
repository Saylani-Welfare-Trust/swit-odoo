from odoo import models, fields


class QurbaniYear(models.Model):
    _name = 'qurbani.hijri'
    _description = 'Hijri Master'

    hijri = fields.Char(string="Hijri")

   