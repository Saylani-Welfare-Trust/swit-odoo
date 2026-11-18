from odoo import models, fields


class POSPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'


    is_donation_in_kind = fields.Boolean('Is Donation In Kind')
    show_popup = fields.Boolean('Show Popup')
    is_bank = fields.Boolean('Is Bank')