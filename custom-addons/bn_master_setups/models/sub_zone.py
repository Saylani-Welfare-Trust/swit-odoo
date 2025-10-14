from odoo import fields, models, _, api, exceptions


class SubZone(models.Model):
    _name = 'sub.zone'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Sub Zone"


    name = fields.Char('Name', tracking=True)

    city_id = fields.Many2one('res.company', string="Company ID", tracking=True)
    
    zone_ids = fields.Many2many('res.company', string="Zone IDs", tracking=True)