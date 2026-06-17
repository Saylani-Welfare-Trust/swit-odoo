from odoo import models, fields


class AnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'


    location_option_id = fields.Many2one('location.option', string="Location Option", tracking=True)

    address = fields.Text('Address', tracking=True)

    analytical_product_line_ids = fields.One2many('analytical.product.line', 'analytic_account_id', string="Analytical Product Lines")