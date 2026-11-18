from odoo import models, fields


class POSOrder(models.Model):
    _inherit = 'pos.order'


    source_document = fields.Char('Source Document')
    
    pos_cheque_order_id = fields.Integer('POS Cheque Order Id')
    
    qurbani = fields.Boolean('Qurbani', default=False)
    receive_voucher = fields.Boolean('Receive Voucher', default=False)

    pos_order_seq = fields.Char('Custom POS Order Seq')

    def _branch(self):
        """The Branch the order is tagged with: its session's (the shop's)."""
        self.ensure_one()
        return self.session_id.analytic_account_id or self.config_id.analytic_account_id

    def _branch_code(self):
        """Branch code of the DN # and order references: the shop's branch."""
        return self._branch().code or 'UNK'


    def _order_fields(self, ui_order):
        """To get the value of field in pos session to pos order"""
        res = super(POSOrder, self)._order_fields(ui_order)

        res['pos_cheque_order_id'] = ui_order.get('pos_cheque_order_id') or False
        res['source_document'] = ui_order.get('source_document') or False
        res['receive_voucher'] = ui_order.get('receive_voucher') or False
        res['pos_order_seq'] = ui_order.get('pos_order_seq') or False
        res['qurbani'] = ui_order.get('qurbani') or False

        return res
