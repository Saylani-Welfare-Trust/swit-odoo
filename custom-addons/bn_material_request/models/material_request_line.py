# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class MemberApprovalLine(models.Model):
    _name = 'material.request.line'
    _description = 'Member Approval Line'

    slaughter_id = fields.Many2one('livestock.slaugther', string='Slaughter Record')
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
            
    
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        store=True, 
        readonly=False,
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

            line._populate_bom_lines()

    def _populate_bom_lines(self):
        self.ensure_one()
        if not self.product_id or not self.approval_id:
            return

        product = self.product_id
        bom = self.env['mrp.bom'].search([
            '|',
            ('product_id', '=', product.id),
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
        ], limit=1)

        if not bom or not bom.bom_line_ids:
            return

        existing_products = self.approval_id.line_ids.filtered(lambda l: l.id != self.id).mapped('product_id.id')
        for bom_line in bom.bom_line_ids:
            bom_product = bom_line.product_id
            if not bom_product or bom_product.id in existing_products:
                continue

            self.approval_id.line_ids.create({
                'approval_id': self.approval_id.id,
                'product_id': bom_product.id,
                'quantity': bom_line.product_qty,
                'analytic_account_id': bom_product.analytic_account_id.id if bom_product.analytic_account_id else False,
                'budget_id': bom_product.analytic_account_id.default_budget_id.id if bom_product.analytic_account_id and bom_product.analytic_account_id.default_budget_id else False,
                'slaughter_id': self.slaughter_id.id if self.slaughter_id else False,
            })

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
            
