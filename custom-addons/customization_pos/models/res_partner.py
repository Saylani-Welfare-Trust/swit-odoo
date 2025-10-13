from odoo import models, fields


class ResPartnerModel(models.Model):
    _inherit = 'res.partner'
    bank_name = fields.Char(string='Bank Name')
    cheque_number = fields.Char(string='Cheque Number')
   
   
