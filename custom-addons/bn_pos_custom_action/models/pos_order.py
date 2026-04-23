from odoo import models, fields
from odoo.exceptions import UserError


class POSOrder(models.Model):
    _inherit = 'pos.order'


    source_document = fields.Char('Source Document')
    remarks = fields.Char('Remarks')


    def _order_fields(self, ui_order):
        """To get the value of field in pos session to pos order"""
        res = super(POSOrder, self)._order_fields(ui_order)

        res['source_document'] = ui_order.get('source_document') or False
        res['remarks'] = ui_order.get('remarks') or False

        return res
    
    def write(self, vals):
        if 'remarks' in vals and not self.env.user.has_group('bn_pos_custom_action.pos_order_remark_group'):
            raise UserError("You cannot edit remarks.")
        return super().write(vals)