from odoo import models, fields


class DisbursementCategory(models.Model):
    _name = 'disbursement.category'
    _description = 'Disbursement Category'


    name = fields.Char('Name')