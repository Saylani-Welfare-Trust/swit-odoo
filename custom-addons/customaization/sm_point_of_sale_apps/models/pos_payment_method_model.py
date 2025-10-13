from odoo import api, fields, models, _


class POSPaymentMethodModelInherit(models.Model):
    _inherit = 'pos.payment.method'

    stock_in = fields.Boolean(string='Stock In')

