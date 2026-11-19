from odoo import models, fields, api


class AnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'


    location_option_id = fields.Many2one('location.option', string="Location Option", tracking=True)

    address = fields.Text('Address', tracking=True)

    # City > Zone > Branch, read from the account and its parents
    city_id = fields.Many2one(
        'account.analytic.account', string='City', compute='_compute_location_levels',
        store=True, recursive=True, index='btree_not_null',
        help='The City of this account: itself when it is a City, else the City above it.')
    zone_id = fields.Many2one(
        'account.analytic.account', string='Zone', compute='_compute_location_levels',
        store=True, recursive=True, index='btree_not_null',
        help='The Zone of this account: itself when it is a Zone, else the Zone above it.')

    @api.depends('location_option_id.name', 'parent_id.city_id', 'parent_id.zone_id')
    def _compute_location_levels(self):
        for account in self:
            level = (account.location_option_id.name or '').strip()
            parent = account.parent_id
            account.city_id = account if level == 'City' else parent.city_id
            account.zone_id = account if level == 'Zone' else (
                False if level == 'City' else parent.zone_id)

    def write(self, vals):
        res = super().write(vals)
        # record rules read the City / Zone of the users' Branch: they are cached
        if {'parent_id', 'location_option_id'} & set(vals):
            self.env.registry.clear_cache()
        return res
    
    @api.depends('name')
    def _compute_display_name(self):
        # Override the default display_name to only show the main name
        # instead of the complete hierarchical path.
        for account in self:
            account.display_name = account.name or ''