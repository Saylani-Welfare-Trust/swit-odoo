from odoo import models, fields


class POSOrder(models.Model):
    _inherit = 'pos.order'


    source_document = fields.Char('Source Document')


    def _order_fields(self, ui_order):
        """To get the value of field in pos session to pos order"""
        res = super(POSOrder, self)._order_fields(ui_order)

        res['source_document'] = ui_order.get('source_document') or False
        
        return res