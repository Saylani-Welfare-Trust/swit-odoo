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

    user_id = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user, readonly=True, tracking=True)
    
    allowed_product_category_ids = fields.Many2many(
        'product.category',
        related='user_id.allowed_product_category_ids',
        string='Allowed Category',
        readonly=True,
        store=False
    )

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price