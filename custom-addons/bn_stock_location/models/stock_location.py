from odoo import api, fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    # The Branch (or Zone / City) the location belongs to: its users see it
    # (res.users.scope_location_ids).
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", tracking=True)
    location_option_id = fields.Many2one('location.option', string="Location Option", tracking=True)

    is_slaughter_location = fields.Boolean('Is Slaughter Location', tracking=True)
    is_distribution_location = fields.Boolean('Is Distribution Location', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if any(vals.get('analytic_account_id') for vals in vals_list):
            self.env['res.users']._scope_changed()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'analytic_account_id' in vals:
            self.env['res.users']._scope_changed()
        return res
