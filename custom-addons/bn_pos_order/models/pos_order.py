from odoo import models, fields, api


class POSOrder(models.Model):
    _inherit = 'pos.order'


    state = fields.Selection(
        [('draft', 'New'), ('cancel', 'Cancelled'), ('refund_request', 'Refund Request'), ('cfo_approval', 'CFO Approval'), ('paid', 'Paid'), ('done', 'Posted'), ('invoiced', 'Invoiced')],
        'Status', readonly=True, copy=False, default='draft', index=True)
    
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", compute="_set_employee_branch", store=True)
    

    def action_refund_request(self):
        self.state = 'refund_request'

    def action_cfo_approval(self):
        self.state = 'cfo_approval'

    @api.depends('user_id')
    def _set_employee_branch(self):
        if self.user_id:
            self.analytic_account_id = self.user_id.employee_id.analytic_account_id.id or None