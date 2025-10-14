from odoo import api, fields, models, _
from odoo.tools import float_compare, float_is_zero
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    cheque_attachment = fields.Binary('Cheque Attachment')
    
    @api.model
    def create_from_ui(self, orders, draft=False):
        order_ids = super(PosOrder, self).create_from_ui(orders, draft)
        # raise UserError(str([orders]))
        orders=self.browse([o.get('id') for o in order_ids])
        sale_order_ids=orders.lines.mapped('sale_order_origin_id')
        fee_journal=self.env['account.journal'].search([('name','=','Student Fee')],limit=1)
        if not fee_journal:
            raise UserError("Fee Journal not found")
        journal_entry=self.env['account.move'].search([('ref','in',sale_order_ids.mapped('name')),('journal_id','=',fee_journal.id)])
        journal_entry._reverse_moves([{
            'ref': "Reversal of %s" % journal_entry.name
        }]).action_post()
        # raise UserError(str(journal_entry))
        
        return order_ids