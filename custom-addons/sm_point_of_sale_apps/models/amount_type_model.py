from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AmountTypeModel(models.Model):
    _name = 'amount.type'
    _description = 'Amount Type Model'
    _rec_name = 'name'

    currency_id = fields.Many2one(comodel_name='res.currency', string='Currency', required=True, domain="[('active', '=', True)]")
    name = fields.Char(string="Amount Type", required=True)

    def name_get(self):
        result = []
        for record in self:
            name = f'{record.product_id.name}'
            result.append((record.id, name))
        return result

