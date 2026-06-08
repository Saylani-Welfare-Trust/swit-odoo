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
    currency_id = fields.Many2one(
        'res.currency',
        'Currency',
        default=lambda self: self.env.company.currency_id
    )

    # Product list where is_welfare = True
    allowed_product_ids = fields.Many2many(
        'product.product',
        string="Allowed Products",
        domain="[('product_tmpl_id.is_welfare', '=', True)]"
    )

    active = fields.Boolean(string="Active", default=True)