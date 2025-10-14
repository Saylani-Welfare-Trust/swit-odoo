from odoo import models, api

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_open_vendor_wizard(self):
        # pass the list of selected PO ids, not just one
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vendor-wise Purchase',
            'view_mode': 'form',
            'res_model': 'vendor.purchase.wizard',
            'target': 'new',
            'context': {
                'default_purchase_order_ids': self.ids,
            },
        }
