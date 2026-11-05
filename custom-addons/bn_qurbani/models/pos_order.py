from odoo import models, fields


class POSOrder(models.Model):
    _inherit = 'pos.order'


    favor = fields.Char('Favor')


    def _order_fields(self, ui_order):
        """To get the value of field in pos session to pos order"""
        res = super(POSOrder, self)._order_fields(ui_order)

        res['favor'] = ui_order.get('favor') or False

        return res

    def _pos_documents(self, extra_data):
        res = super()._pos_documents(extra_data)
        qurbani_id = (extra_data.get('qurbani') or {}).get('qurbani_id')
        return res + [self.env['qurbani.order'].browse(qurbani_id).exists() if qurbani_id else self.env['qurbani.order']]
