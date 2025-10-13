from odoo import fields, api, models, exceptions, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_coa_installed = fields.Boolean()
    loan_request_ids = fields.One2many('mfd.loan.request', 'customer_id', string='Loan Request IDs')

    scheme_type_ids = fields.Many2many('mfd.scheme', string="Scheme Type ID")