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
    
    on_hand_qty = fields.Float(
        string='On Hand',
        compute='_compute_on_hand_qty'
    )
    
    @api.depends('product_id', 'approval_id.source_location_id')
    def _compute_on_hand_qty(self):
        for line in self:
            if line.product_id and line.approval_id.source_location_id:
                line.on_hand_qty = line.product_id.with_context(
                    location=line.approval_id.source_location_id.id
                ).qty_available
            else:
                line.on_hand_qty = 0.0
    

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
    
    @api.onchange('budget_id')
    def _onchange_budget_id_update_analytic_default(self):
        """When a budget is manually selected on the line, set it as the default on the analytic account."""
        for line in self:
            if line.budget_id and line.analytic_account_id:
                # Optionally, only update if the analytic account has no default yet
                # or update always to keep them in sync
                if not line.analytic_account_id.default_budget_id:
                    line.analytic_account_id.default_budget_id = line.budget_id.id
                # If you want to always override:
                # line.analytic_account_id.default_budget_id = line.budget_id.id
            
    # Abdul Hai