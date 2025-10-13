from odoo import fields, models, _, api, exceptions


class City(models.Model):
    _name = 'city'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "City"


    name = fields.Char('Name', tracking=True)