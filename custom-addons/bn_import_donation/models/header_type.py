from odoo import fields, models


class HeaderType(models.Model):
    _name = 'header.type'
    _inherit = ['mail.thread']

    name = fields.Char('Name', required=True, tracking=True)