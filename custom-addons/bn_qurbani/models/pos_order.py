from odoo import models, fields


class POSOrder(models.Model):
    _inherit = 'pos.order'


    favor = fields.Char('Favor')


    def _order_fields(self, ui_order):
        """To get the value of field in pos session to pos order"""
        res = super(POSOrder, self)._order_fields(ui_order)

        res['favor'] = ui_order.get('favor') or False

        return res