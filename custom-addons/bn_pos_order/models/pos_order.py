from odoo import models, fields, api


class POSOrder(models.Model):
    _inherit = 'pos.order'


    mobile = fields.Char(related='partner_id.mobile', string="Mobile No.")

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
        for rec in self:
            if rec.user_id:
                rec.analytic_account_id = rec.user_id.employee_id.analytic_account_id.id or None