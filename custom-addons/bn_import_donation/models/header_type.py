from odoo import models, fields


class HeaderType(models.Model):
    _name = 'header.type'
    _description = "Header Type"


    name = fields.Char('Name')