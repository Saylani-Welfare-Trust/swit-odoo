from odoo import models, fields, api


class KeyBunch(models.Model):
    _name = 'key.bunch'
    _description = 'Key Bunch'
    _inherit = ["mail.thread", "mail.activity.mixin"]


    name = fields.Char('Name', tracking=True)
    room_no = fields.Char('Room No.', tracking=True)
    rack_no = fields.Char('Rack No.', tracking=True)
    slot_no = fields.Char('Slot No.', tracking=True)
    shelf_no = fields.Char('Shelf No.', tracking=True)

    city_id = fields.Many2one('account.analytic.account', string="City", tracking=True)
    zone_id = fields.Many2one('account.analytic.account', string="Zone", tracking=True)
    sub_zone_id = fields.Many2one('sub.zone', string="Sub Zone", tracking=True)

    rider_id = fields.Many2one('hr.employee', string="Rider")

    key_ids = fields.One2many('key', 'key_bunch_id', string="Keys")