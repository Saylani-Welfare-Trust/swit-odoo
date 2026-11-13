from odoo import models, fields


class StockLocation(models.Model):
    _inherit = 'stock.location'


    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", tracking=True)
    location_option_id = fields.Many2one('location.option', string="Location Option", tracking=True)

    is_slaughter_location = fields.Boolean('Is Slaughter Location', tracking=True)
    is_distribution_location = fields.Boolean('Is Distribution Location', tracking=True)

    def write(self, vals):
        res = super().write(vals)
        # The Donation Box record rules match a user's allowed locations to cities
        # through this field, and rule domains are cached per user.
        if 'analytic_account_id' in vals:
            self.env.registry.clear_cache()
        return res
