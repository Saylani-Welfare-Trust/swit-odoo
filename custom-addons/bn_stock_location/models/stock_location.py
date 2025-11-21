from odoo import models, fields


class StockLocation(models.Model):
    _inherit = 'stock.location'


    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")