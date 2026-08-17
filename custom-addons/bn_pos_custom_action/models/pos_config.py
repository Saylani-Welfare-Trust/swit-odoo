from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'


    counter = fields.Integer(string="Counter", default="1")
    sequence = fields.Integer(string="Sequence", default="1")