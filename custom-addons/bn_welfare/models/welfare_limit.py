from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class WelfareApprovalLimit(models.Model):
    _name = 'welfare.approval.limit'
    _description = "Welfare Approval Limits"
    _rec_name = 'group_id'

    group_id = fields.Many2one('res.groups', string="User Group", required=True)
    group_name = fields.Char(related='group_id.name', string="Group Name", store=True)
    
    # Limit settings
    max_amount_limit = fields.Monetary(string="Maximum Approval Amount", required=True)
    currency_id = fields.Many2one('res.currency', 'Currency', 
                                  default=lambda self: self.env.company.currency_id)
    
    # Product limits using your product.master
    allowed_product_master_ids = fields.Many2many('product.master', string="Allowed Products")
    
    active = fields.Boolean(string="Active", default=True)