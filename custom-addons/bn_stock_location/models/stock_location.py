from odoo import models, fields


class StockLocation(models.Model):
    _inherit = 'stock.location'


    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", tracking=True)
    location_option_id = fields.Many2one('location.option', string="Location Option", tracking=True)

    is_slaughter_location = fields.Boolean('Is Slaughter Location', tracking=True)
    is_distribution_location = fields.Boolean('Is Distribution Location', tracking=True)