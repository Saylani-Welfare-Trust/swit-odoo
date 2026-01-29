from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import re


class POSOrder(models.Model):
    _inherit = 'pos.order'


    mobile = fields.Char(related='partner_id.mobile', string="Mobile No.")

    state = fields.Selection(
        [('draft', 'New'), ('cancel', 'Cancelled'), ('cfo_approval', 'CFO Approval'), ('paid', 'Paid'), ('done', 'Posted'), ('invoiced', 'Invoiced'), ('refund', 'Refunded'), ('reject', 'Reject')],
        # [('draft', 'New'), ('cancel', 'Cancelled'), ('refund_request', 'Refund Request'), ('cfo_approval', 'CFO Approval'), ('paid', 'Paid'), ('done', 'Posted'), ('invoiced', 'Invoiced'), ('refund', 'Refunded')],
        'Status', readonly=True, copy=False, default='draft', index=True)
    
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", compute="_set_employee_branch", store=True)
    

    @api.constrains('mobile')
    def _check_mobile_number(self):
        for rec in self:
            if rec.mobile:
                if not re.fullmatch(r"\d{10}", rec.mobile):
                    raise ValidationError(
                        "Mobile number must contain exactly 10 digits."
                    )

    def action_reject(self):
        pos_order = self.env['pos.order'].search([('id', '=', self.refunded_order_ids[0].id)])
        
        if pos_order:
            if self.session_id.state == 'closing_control':
                pos_order.state = 'paid'
            else:
                pos_order.state = 'done'
        
        self.state = 'reject'

    # def action_refund_request(self):
    #     self.state = 'refund_request'

    def action_cfo_approval(self):
        self.state = 'cfo_approval'
    
    def refund(self):
        self.state = 'refund'
        return {
            'name': _('Return Products'),
            'view_mode': 'form',
            'res_model': 'pos.order',
            'res_id': self._refund().ids[0],
            'view_id': False,
            'context': self.env.context,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    @api.depends('user_id')
    def _set_employee_branch(self):
        for rec in self:
            if rec.user_id:
                rec.analytic_account_id = rec.user_id.employee_id.analytic_account_id.id or None