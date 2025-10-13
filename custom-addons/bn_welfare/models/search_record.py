from odoo import fields, models


class SearchRecord(models.TransientModel):
    _inherit = 'search.record'


    disbursement_type_id = fields.Many2one('disbursement.type', string="Disbursement Type ID")