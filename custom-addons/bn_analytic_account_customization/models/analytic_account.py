from odoo import models, fields


class AnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'


    location_option_id = fields.Many2one('location.option', string="Location Option")

    address = fields.Text('Address')