from odoo import models, fields, api


class AnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'


    location_option_id = fields.Many2one('location.option', string="Location Option", tracking=True)

    address = fields.Text('Address', tracking=True)
    
    @api.depends('name')
    def _compute_display_name(self):
        # Override the default display_name to only show the main name
        # instead of the complete hierarchical path.
        for account in self:
            account.display_name = account.name or ''