from odoo import models, fields


class City(models.Model):
    _name = 'city'
    _description = "City"


    name = fields.Char('Name')