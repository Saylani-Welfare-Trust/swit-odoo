# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class MemberApprovalLine(models.Model):
    _name = 'material.request.line'
    _description = 'Member Approval Line'
    
    is_shariah_compliant = fields.Boolean('Shariah Law Compliant', compute='_compute_shariah_compliance', store=True)


    
    budget_id = fields.Many2one('budget.budget', string='Budgetary Position', help='Budgetary position for this product line.')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', help='Analytic account for this product line.')
    approval_id = fields.Many2one('material.request', string='Approval', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id', readonly=True)
    quantity = fields.Float('Quantity', default=1.0, required=True)
    unit_price = fields.Float('Unit Price', related='product_id.lst_price', store=True)
    subtotal = fields.Float('Subtotal', compute='_compute_subtotal', store=True)
    
    @api.depends('analytic_account_id')
    def _compute_shariah_compliance(self):
        for line in self:
            if line.analytic_account_id:
                # Check if analytic_account_id is present in shariah.law
                shariah = line.env['shariah.law'].search([
                    ('analytic_account_id', '=', line.analytic_account_id.id)
                ], limit=1)
                line.is_shariah_compliant = bool(shariah)
            else:
                line.is_shariah_compliant = False

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price