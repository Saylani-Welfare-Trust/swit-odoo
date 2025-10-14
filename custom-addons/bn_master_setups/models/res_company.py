from odoo import fields, models, _, api, exceptions

type_selection = [
    ('branch', 'Branch'),
    ('state', 'state'),
    ('city', 'City'),
    ('zone', 'Zone'),
    ('location', 'Location'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'


    type_selection = fields.Selection(selection=type_selection, string="Type")

    location_type_ids = fields.Many2many('location.type', string="Location Type")

    prefix = fields.Char('Prefix', tracking=True)