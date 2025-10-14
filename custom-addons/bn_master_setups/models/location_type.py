from odoo import fields, models, _, api, exceptions


class LocationType(models.Model):
    _name = 'location.type'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Location Type"


    name = fields.Char('Name', tracking=True)