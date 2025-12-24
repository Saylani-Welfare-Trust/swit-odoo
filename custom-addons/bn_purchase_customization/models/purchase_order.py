from odoo import models, fields


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'


    # state = fields.Selection([
    #     ('draft', 'RFQ'),
    #     ('sent', 'RFQ Sent'),
    #     ('to approve', 'To Approve'),
    #     ('purchase', 'Purchase Order'),
    #     ('done', 'Locked'),
    #     ('cancel', 'Cancelled')
    # ], string='Status', readonly=True, index=True, copy=False, default='draft', tracking=True)