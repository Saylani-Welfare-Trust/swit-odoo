# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class KeyBunch(models.Model):
    _name = 'key.bunch'
    _description = 'Key Bunch'
    _inherit = ["mail.thread", "mail.activity.mixin", "bn.city.access.mixin"]

    name = fields.Char('Name', tracking=True)
    room_no = fields.Char('Room No.', tracking=True)
    rack_no = fields.Char('Rack No.', tracking=True)
    slot_no = fields.Char('Slot No.', tracking=True)
    shelf_no = fields.Char('Shelf No.', tracking=True)

    city_id = fields.Many2one('account.analytic.account', string="City", tracking=True)
    zone_id = fields.Many2one('account.analytic.account', string="Zone", tracking=True)
    sub_zone_id = fields.Many2one('sub.zone', string="Sub Zone", tracking=True)

    key_ids = fields.One2many('key', 'key_bunch_id', string="Keys")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._bn_check_city(vals.get('city_id'))
        return super().create(vals_list)

    def write(self, vals):
        self._bn_check_city(vals.get('city_id'))
        return super().write(vals)

    def unlink(self):
        for bunch in self:
            if bunch.key_ids.filtered(lambda k: k.state != 'closed'):
                raise UserError(_('Bunch "%s" still contains keys and cannot be deleted.') % bunch.display_name)
        return super().unlink()
