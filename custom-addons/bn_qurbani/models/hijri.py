from odoo import models, fields


class Hijri(models.Model):
    _name = 'hijri'
    _description = 'Hijri'


    name = fields.Char('Hijri')