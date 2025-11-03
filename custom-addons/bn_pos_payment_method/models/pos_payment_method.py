from odoo import models, fields


class POSPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'


    show_popup = fields.Boolean('Show Popup')
    is_bank = fields.Boolean('Is Bank')