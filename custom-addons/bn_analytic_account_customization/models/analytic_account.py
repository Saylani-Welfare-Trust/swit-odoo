from odoo import models, fields


class AnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    location_option_id = fields.Many2one('location.option', string="Location Option", tracking=True)
    address = fields.Text('Address', tracking=True)
    parent_id = fields.Many2one('account.analytic.account', string="Parent City", tracking=True,
                                 domain="[('location_option_id.name', '=', 'City')]")