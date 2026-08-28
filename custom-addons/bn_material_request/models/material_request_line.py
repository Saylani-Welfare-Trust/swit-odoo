# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class MemberApprovalLine(models.Model):
    _name = 'material.request.line'
    _description = 'Member Approval Line'
    
    
    budget_id = fields.Many2one('budget.budget', string='Budgetary Position', help='Budgetary position for this product line.')
    approval_id = fields.Many2one('material.request', string='Approval', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id', readonly=True)
    quantity = fields.Float('Quantity', default=1.0, required=True)
    unit_price = fields.Float('Unit Price', related='product_id.lst_price', store=True)
    subtotal = fields.Float('Subtotal', compute='_compute_subtotal', store=True)

    allowed_product_category_ids = fields.Many2many(
        related='approval_id.user_id.allowed_product_category_ids',
        readonly=True
    )

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price
            
    # Abdul Hai
    
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        store=True,                                 # stored in DB
        readonly=False,                              # allow manual override if needed (optional)
        domain=[('plan_id.name', '=', 'Segment')],
    )
    

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Set analytic account and default budget from product's analytic account."""
        for line in self:
            product = line.product_id
            if product:
                line.analytic_account_id = product.analytic_account_id
                if product.analytic_account_id:
                    line.budget_id = product.analytic_account_id.default_budget_id
                else:
                    line.budget_id = False
            else:
                line.analytic_account_id = False
                line.budget_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'product_id' in vals:
                product = self.env['product.product'].browse(vals['product_id'])
                if product and product.analytic_account_id:
                    if not vals.get('analytic_account_id'):
                        vals['analytic_account_id'] = product.analytic_account_id.id
                    if not vals.get('budget_id'):
                        vals['budget_id'] = product.analytic_account_id.default_budget_id.id
        return super().create(vals_list)
            
    # Abdul Hai