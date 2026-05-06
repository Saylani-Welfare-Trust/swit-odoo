from odoo import models, fields
from odoo.exceptions import UserError


class POSOrder(models.Model):
    _inherit = 'pos.order'


    source_document = fields.Char('Source Document')
    
    qurbani = fields.Boolean('Qurbani', default=False)
    receive_voucher = fields.Boolean('Receive Voucher', default=False)


    def _order_fields(self, ui_order):
        """To get the value of field in pos session to pos order"""
        res = super(POSOrder, self)._order_fields(ui_order)

        res['source_document'] = ui_order.get('source_document') or False
        res['receive_voucher'] = ui_order.get('receive_voucher') or False
        res['qurbani'] = ui_order.get('qurbani') or False

        return res