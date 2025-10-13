from odoo import fields, models


class SearchRecord(models.TransientModel):
    _inherit = 'search.record'


    scheme_type_id = fields.Many2one('mfd.scheme', string="Scheme Type ID")