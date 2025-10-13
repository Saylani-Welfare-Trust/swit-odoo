from odoo import fields, models


class ResCity(models.Model):
    _name = 'res.city'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Res City"


    name = fields.Char('Name', tracking=True)