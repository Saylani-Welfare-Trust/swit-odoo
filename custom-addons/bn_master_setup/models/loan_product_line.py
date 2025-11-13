from odoo import models, fields


class LoanProductLine(models.Model):
    _name = 'loan.product.line'


    product_id = fields.Many2one('product.product', string='Product')
    microfinance_scheme_line_id = fields.Many2one('microfinance.scheme.line', string='Microfinance Scheme Line')

    sd_amount = fields.Float('SD Amount')
    inst_amount = fields.Float('Ins. Amount')

    product_ids = fields.Many2many('product.product', string='Products')
    
    is_recover = fields.Boolean('Is Recover?')
    