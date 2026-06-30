from odoo import models, fields


class AnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'



    product_ids = fields.Many2many('analytical.product.line', string="Products")