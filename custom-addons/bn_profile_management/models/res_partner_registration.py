# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartnerRegistration(models.Model):
    """The unique ID a contact received for one of its tags (Donor, Donee,
    Welfare ...). One contact per person; one ID per tag. The format comes
    from the tag's Registration ID Pattern."""
    _name = 'res.partner.registration'
    _description = 'Profile Registration ID'
    _order = 'date desc, id desc'
    _rec_name = 'code'

    partner_id = fields.Many2one('res.partner', string='Contact', required=True, index=True, ondelete='cascade')
    category_id = fields.Many2one('res.partner.category', string='Tag', required=True, index=True, ondelete='restrict')
    code = fields.Char('Registration ID', required=True, index=True)
    date = fields.Date('Registered On', default=fields.Date.context_today)
    user_id = fields.Many2one('res.users', string='Registered By', default=lambda self: self.env.user)

    _sql_constraints = [
        ('partner_category_uniq', 'unique(partner_id, category_id)',
         'A contact can only have one Registration ID per tag.'),
        ('category_code_uniq', 'unique(category_id, code)',
         'This Registration ID is already used for this tag.'),
    ]
