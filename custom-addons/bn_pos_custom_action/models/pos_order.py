from odoo import models, fields
from odoo.exceptions import UserError


class POSOrder(models.Model):
    _inherit = 'pos.order'


    source_document = fields.Char('Source Document')
    
    pos_cheque_order_id = fields.Integer('POS Cheque Order Id')
    
    qurbani = fields.Boolean('Qurbani', default=False)
    receive_voucher = fields.Boolean('Receive Voucher', default=False)


    def _order_fields(self, ui_order):
        """To get the value of field in pos session to pos order"""
        res = super(POSOrder, self)._order_fields(ui_order)

        res['pos_cheque_order_id'] = ui_order.get('pos_cheque_order_id') or False
        res['source_document'] = ui_order.get('source_document') or False
        res['receive_voucher'] = ui_order.get('receive_voucher') or False
        res['qurbani'] = ui_order.get('qurbani') or False

        return res