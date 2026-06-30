from odoo import models, fields


class Hijri(models.Model):
    _name = 'hijri'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = 'Hijri'


    name = fields.Char('Hijri', tracking=True)