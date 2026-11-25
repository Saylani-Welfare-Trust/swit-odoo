from odoo import models, fields


class HeaderType(models.Model):
    _name = 'header.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Header Type"


    name = fields.Char('Name')