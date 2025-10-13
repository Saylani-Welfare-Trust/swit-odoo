from odoo import fields, models


class ConfirmSearch(models.TransientModel):
    _inherit = 'confirm.search'


    scheme_type_id = fields.Many2one('mfd.scheme', string="Scheme Type ID")