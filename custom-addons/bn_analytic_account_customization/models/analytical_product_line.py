from odoo import models, fields


class AnalyticalProductLine(models.Model):
    _name = 'analytical.product.line'
    _description = "Analytical Product Line"


    product_id = fields.Many2one('product.product', string="Product")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")