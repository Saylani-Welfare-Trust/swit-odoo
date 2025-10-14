from odoo import fields, models, api, exceptions


class POSOrder(models.Model):
    _inherit = 'pos.order'


    remarks = fields.Text('Remarks')

    state = fields.Selection(
        [('draft', 'New'), ('cancel', 'Cancelled'),('cfo_approval', 'CFO Approval'), ('paid', 'Paid'), ('refund_request', 'Refund Request'), ('head_approval', 'Head Approval'), ('done', 'Posted'), ('invoiced', 'Invoiced')],
        'Status', readonly=True, copy=False, default='draft', index=True)

    def action_refund_request(self):
        if not self.remarks:
            raise exceptions.ValidationError('Please add remarks')
        
        self.state = 'refund_request'
    
    def action_head_approval(self):
        self.state = 'head_approval'

    def refund(self):
        self.state = 'draft'

        super(POSOrder, self).refund()