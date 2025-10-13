from odoo import fields, models, _, exceptions, api


class POSOrder(models.Model):
    _inherit = 'pos.order'


    transaction_id = fields.Char('Transaction ID')
    qr_code = fields.Char('QR Code')