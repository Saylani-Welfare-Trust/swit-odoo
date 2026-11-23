from odoo import models, fields


class City(models.Model):
    _name = 'city'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "City"


    name = fields.Char('Name')