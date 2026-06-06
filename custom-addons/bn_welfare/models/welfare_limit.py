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
    disbursement_application_type_id = fields.Many2one(
        'disbursement.application.type', 
        string="Disbursement Application Type"
    )

    # Product domain filter
    product_domain = fields.Char(
        string="Product Domain",
        compute='_compute_product_domain',
        store=True,
        default="[]"
    )

    active = fields.Boolean(string="Active", default=True)

    @api.depends('disbursement_application_type_id.product_category_id')
    def _compute_product_domain(self):
        for rec in self:
            products = self.env['product.product'].search([
                ('product_tmpl_id.is_welfare', '=', True),
            ])
            rec.product_domain = str([('id', 'in', products.ids)])