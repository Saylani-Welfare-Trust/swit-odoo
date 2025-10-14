from odoo import models, fields,api
from odoo.exceptions import UserError




class MakePayment(models.TransientModel):
    _inherit='pos.make.payment'

    def _default_user_check(self):
        active_id = self.env.context.get('active_id')
        order_id = self.env['pos.order'].browse(active_id)
        if order_id.check_user:
            return True
        else:
            return False
    
    def _default_user_request(self):
        active_id = self.env.context.get('active_id')
        order_id = self.env['pos.order'].browse(active_id)
        if order_id.request_sent:
            return True
        else:
            return False
    def _default_request_approved(self):
        active_id = self.env.context.get('active_id')
        order_id = self.env['pos.order'].browse(active_id)
        if order_id.approved:
            return True
        else:
            return False
    
    def _default_is_admin_user(self):
        approval = self.env['approval.workflow'].search([('active_approval','=',True)],limit=1)
        
        if approval and approval.users:
            for rec in approval.users:
                if rec.id == self.env.user.id:
                    return True
                else:
                    return False
    
    def _default_order(self):
        active_id = self.env.context.get('active_id')
        order_id = self.env['pos.order'].browse(active_id)
        return order_id.id
        
    approval_user = fields.Boolean(string="Approval",default=_default_user_check)
    request_sent= fields.Boolean(string="Request Sent", default=_default_user_request)
    approved = fields.Boolean(string='Approve',default=_default_request_approved)

    is_admin_user = fields.Boolean(string="is_admin",default=_default_is_admin_user)

    pos_order = fields.Many2one('pos.order',string="Order",readonly=True,default=_default_order)


    # def action_request(self):
    #     active_id = self.env.context.get('active_id')
    #     order_id = self.env['pos.order'].browse(active_id)
    #     approval = self.env['approval.workflow'].search([('active_approval','=',True)],limit=1)
    #     users_list = []
    #     if approval and approval.users:
    #         for rec in approval.users:
    #             if rec.partner_id.email:
    #                 users_list.append(rec.partner_id.email)
    #         template = self.env.ref('advance_donation.email_template_refund_request')
    #         base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url',default='')
    #         record_url = "{}/web#id={}&view_type=form&model={}".format(
    #             base_url,
    #             order_id.id,
    #             order_id._name
    #         )
            

            
    #         email = ",".join(users_list)
    #         email_values = {
    #         "email_to":email,
    #         "user_name":str(self.env.user.name),
    #         "ticket":str(order_id.name) ,
    #         "record_url":record_url,
    #         }
    #         template.with_context(
    #             email_values) \
    #             .send_mail(self.id, force_send=True)
    #         order_id.approva_state = "pending"
    #         order_id.request_sent=True
            
    def action_request(self):
        active_id = self.env.context.get('active_id')
        
        if not active_id:
            
            raise UserError("No active record found in the context.")
        
        order_id = self.env['pos.order'].browse(active_id)
       
        
        if not order_id.exists():
            raise UserError("The POS Order record does not exist or has been deleted.")
        
        approval = self.env['approval.workflow'].search([('active_approval', '=', True)], limit=1)
        if not approval or not approval.users:
            raise UserError("No active approval workflow found or no users assigned.")
        
        users_list = [
            rec.partner_id.email for rec in approval.users if rec.partner_id.email
        ]
        if not users_list:
            raise UserError("No users with email addresses found in the approval workflow.")

        # Fetch email template
        template = self.env.ref('advance_donation.email_template_refund_request')
    
        
        if not template:
            raise UserError("Email template 'advance_donation.email_template_refund_request' not found.")

        # Prepare data
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', default='')
        record_url = "{}/web#id={}&view_type=form&model={}".format(base_url, order_id.id, order_id._name)
        email = ",".join(users_list)
        email_values = {
            "email_to": email,
            "user_name": str(self.env.user.name),
            "ticket": str(order_id.name),
            "record_url": record_url,
        }
      
        
        # Send email
        template.with_context(email_values).sudo().send_mail(self.id, force_send=True)

        # Update order state
        order_id.write({
            "approva_state": "pending",
            "request_sent": True,
        })




        

        

    def action_approved(self):

        active_id = self.env.context.get('active_id')
        order_id = self.env['pos.order'].browse(active_id)
        order_id.approva_state = "approved"
        order_id.approved = True

        
    
    def reject(self):
        
        active_id = self.env.context.get('active_id')
        order_id = self.env['pos.order'].browse(active_id)
        order_id.approva_state = "draft"
        order_id.approved = False

     

    