from odoo import models, fields


assest_selection = [
    ('cash', 'Cash'),
    ('movable_asset', 'Movable Asset'),
    ('immovable_asset', 'Immovable Asset')
]


class MicrofinanceSchemeLine(models.Model):
    _name = 'microfinance.scheme.line'
    _description = "Microfinance Scheme Line"


    microfinance_scheme_id = fields.Many2one('microfinance.scheme')

    name = fields.Char('Application Name')
    asset_type = fields.Selection(selection=assest_selection, string='Asset Type', default='cash')

    loan_product_line_ids = fields.One2many('loan.product.line', 'microfinance_scheme_line_id', string='Product')