from odoo import fields, models, api, exceptions


class KeyLocaiton(models.Model):
    _name = 'key.location'
    _description = 'Key Location'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "group_name"


    city_id = fields.Many2one('res.company', string="City ID", tracking=True)
    zone_id = fields.Many2one('res.company', string="Zone ID", default=lambda self: self.env.company.id, tracking=True)
    sub_zone_id = fields.Many2one('sub.zone', string="Sub Zone ID", tracking=True)

    room_no = fields.Char('Room No.', tracking=True)
    rack_no = fields.Char('Rack No.', tracking=True)
    shelf_no = fields.Char('Shelf No.', tracking=True)
    slot_no = fields.Char('Slot No.', tracking=True)
    group_name = fields.Char('Group Name', tracking=True)
    name = fields.Char('Name', compute="_set_name", store=True, tracking=True)
    rec_name = fields.Char('Rec Name', compute="_set_rec_name", store=True, tracking=True)

    key_ids = fields.One2many('key', 'key_location_id', string="Key IDs")


    @api.depends('city_id', 'zone_id', 'sub_zone_id', 'room_no', 'rack_no', 'shelf_no', 'slot_no')
    def _set_name(self):
        for rec in self:
            rec.name = f'{rec.city_id.name}->{rec.zone_id.name}->{rec.sub_zone_id.name}->R-{rec.room_no}->RC-{rec.rack_no}->S-{rec.shelf_no}->SL-{rec.slot_no}'
    
    @api.depends('room_no', 'rack_no', 'shelf_no', 'slot_no')
    def _set_rec_name(self):
        for rec in self:
            rec.rec_name = f'R-{rec.room_no}->RC-{rec.rack_no}->S-{rec.shelf_no}->SL-{rec.slot_no}'