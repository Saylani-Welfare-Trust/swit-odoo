from odoo import models, fields


class DisbursementBank(models.Model):
    _name = 'disbursement.bank'

    name = fields.Char(string='Name')
    is_active = fields.Boolean(string='Active')