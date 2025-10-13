from odoo import fields, models, _, api, exceptions


class Zone(models.Model):
    _name = 'zone'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Zone"


    name = fields.Char('Name', tracking=True)

    city_ids = fields.Many2many('city', string="City IDs", tracking=True)

class ResCompany(models.Model):
    _inherit = 'res.company'


    city_ids = fields.Many2many('city', string="City IDs", tracking=True)