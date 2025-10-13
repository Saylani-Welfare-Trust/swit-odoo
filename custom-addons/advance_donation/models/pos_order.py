from odoo import models, fields,api
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    approva_state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending for Approval'),
        ('approved', 'Approved')
    ], 'Approval Status', track_visibility='onchange', copy=False, default='draft')
    
    user_approve_boolean = fields.Boolean(
        'User Approved',compute="check_user_access")
    check_user = fields.Boolean('Check')
    request_sent = fields.Boolean("Request Sent",default=False)

    approved = fields.Boolean(string='Approve')
 
    def check_user_access(self):
        approval = self.env['approval.workflow'].search([('active_approval','=',True)],limit=1)
        self.env.user
        if approval and approval.users:
            for rec in approval.users:
                if rec.id == self.env.user.id:
                    self.user_approve_boolean = True
                    self.check_user = True
                    break
                else:
                    self.user_approve_boolean = False
                    self.check_user = False
                    
        else:
            self.user_approve_boolean = False
            self.check_user = False
    def action_cfo_approval(self):
        for order in self:
            order.state = 'cfo_approval'

    def action_paid(self):
        for order in self:
            order.state = 'paid'
    def action_draft(self):
        for order in self:
            order.state = 'draft'
    

