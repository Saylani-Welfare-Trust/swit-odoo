# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    product_template_id = fields.Many2one(
        related='product_id.product_tmpl_id',
        store=True,
        readonly=False,
        domain=[('sale_ok', '=', True)],
    )

    @api.onchange('product_template_id')
    def _onchange_product_template_id(self):
        if not self.product_template_id:
            return

        # Get all product.product variants for this template
        products = self.env['product.product'].search([
            ('product_tmpl_id', '=', self.product_template_id.id)
        ])

        # Get distribution models for any matching product variant
        distribution_model = self.env['account.analytic.distribution.model'].search([
            ('product_id', 'in', products.ids)
        ], limit=1)  # Adjust logic if multiple variants should be considered

        if distribution_model:
            self.analytic_distribution = distribution_model.analytic_distribution


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.onchange('product_id')
    def _onchange_product_id_set_analytic_distribution(self):
        if not self.product_id:
            return

        # Find a distribution model for the selected product
        distribution_model = self.env['account.analytic.distribution.model'].search([
            ('product_id', '=', self.product_id.id)
        ], limit=1)

        if distribution_model:
            self.analytic_distribution = distribution_model.analytic_distribution