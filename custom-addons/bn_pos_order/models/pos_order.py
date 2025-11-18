from odoo import models, fields


class POSOrder(models.Model):
    _inherit = 'pos.order'


    state = fields.Selection(
        [('draft', 'New'), ('cancel', 'Cancelled'), ('refund_request', 'Refund Request'), ('cfo_approval', 'CFO Approval'), ('paid', 'Paid'), ('done', 'Posted'), ('invoiced', 'Invoiced')],
        'Status', readonly=True, copy=False, default='draft', index=True)
    

    def action_refund_request(self):
        self.state = 'refund_request'

    def action_cfo_approval(self):
        self.state = 'cfo_approval'