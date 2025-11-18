from odoo import models, fields


class LoanProductLine(models.Model):
    _inherit = 'loan.product.line'


    product_id = fields.Many2one('product.product', string='Product', domain="[('is_microfinance', '=', True)]")

    product_ids = fields.Many2many('product.product', string='Products', domain="[('is_microfinance', '=', True)]")