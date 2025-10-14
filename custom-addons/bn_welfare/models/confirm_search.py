from odoo import fields, models


class ConfirmSearch(models.TransientModel):
    _inherit = 'confirm.search'


    disbursement_type_id = fields.Many2one('disbursement.type', string="Disbursement Type ID")