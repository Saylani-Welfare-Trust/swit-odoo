# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProfileViewField(models.Model):
    """One field of a Profile Type's list, search or form view, in the
    position chosen by the administrator (drag the handle)."""
    _name = 'profile.view.field'
    _description = 'Profile View Field'
    _order = 'sequence, id'

    category_id = fields.Many2one('res.partner.category', string='Profile Type', required=True,
                                  ondelete='cascade', index=True)
    view_type = fields.Selection([('list', 'List'), ('search', 'Search'), ('form', 'Form')],
                                 required=True, index=True)
    sequence = fields.Integer(default=10)
    field_id = fields.Many2one('ir.model.fields', string='Field', required=True, ondelete='cascade',
                               domain=lambda self: self.env['res.partner.category']._profile_field_domain())
    field_name = fields.Char(related='field_id.name', string='Technical Name')

    _sql_constraints = [
        ('field_uniq', 'unique(category_id, view_type, field_id)',
         'A field can only be once in the same view of a Profile Type.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.category_id._profile_sync_m2m_from_lines()
        return lines

    def write(self, vals):
        categories = self.category_id
        res = super().write(vals)
        (categories | self.category_id)._profile_sync_m2m_from_lines()
        return res

    def unlink(self):
        categories = self.category_id
        res = super().unlink()
        categories.exists()._profile_sync_m2m_from_lines()
        return res
