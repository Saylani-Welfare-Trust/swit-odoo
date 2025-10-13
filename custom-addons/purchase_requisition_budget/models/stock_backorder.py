# from odoo import models, fields, api
#
#
# class StockBackorderConfirmation(models.TransientModel):
#     _inherit = 'stock.backorder.confirmation'
#
#     # def process(self):
#     #     res = super().process()
#     #     picking = self.pick_ids
#     #     if picking:
#     #         requisition = self.env['employee.purchase.requisition'].search([('backorder_picking_id', '=', picking.id)], limit=1)
#     #         if requisition:
#     #             requisition.write({'state': 'received'})
#     #             backorder_picking = picking.backorder_ids
#     #             if backorder_picking:
#     #                 requisition.write({'backorder_picking_id': backorder_picking.id})
#     #
#     #     return res
