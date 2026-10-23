from odoo import models, fields


class StockLocation(models.Model):
    _inherit = 'stock.location'


    cow_sequence_number = fields.Integer('Cow Sequence Number', default=1)
    goat_sequence_number = fields.Integer('Goat Sequence Number', default=1)