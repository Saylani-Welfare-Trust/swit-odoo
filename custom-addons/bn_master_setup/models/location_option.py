from odoo import models, fields


class LocationOption(models.Model):
    _name = 'location.option'
    _description = "Location Option"


    name = fields.Char('Name')