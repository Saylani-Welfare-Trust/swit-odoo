from odoo import fields, models


class DNCoverImage(models.Model):
    _name = 'dn.cover.image'
    _inherit = ['mail.thread']
    _description = 'DN Cover Image'


    name = fields.Char('Name')
    image = fields.Binary('Cover Image')