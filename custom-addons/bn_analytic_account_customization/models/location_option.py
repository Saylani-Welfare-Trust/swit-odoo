from odoo import models, fields


class LocationOption(models.Model):
    _name = 'location.option'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Location Option"


    name = fields.Char('Name')