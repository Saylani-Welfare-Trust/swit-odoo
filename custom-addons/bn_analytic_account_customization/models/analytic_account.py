from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Location Option of each level, top first: a Zone sits under a City, a Branch
# under a Zone (or directly under its City).
LEVELS = ('City', 'Zone', 'Branch')
ALLOWED_PARENTS = {'Zone': ('City',), 'Branch': ('Zone', 'City')}


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
    product_template_count = fields.Integer('Products', compute='_compute_product_template_count')

    @api.depends('location_option_id.name', 'parent_id.city_id', 'parent_id.zone_id')
    def _compute_location_levels(self):
        for account in self:
            level = (account.location_option_id.name or '').strip()
            parent = account.parent_id
            account.city_id = account if level == 'City' else parent.city_id
            account.zone_id = account if level == 'Zone' else (
                False if level == 'City' else parent.zone_id)

    @api.constrains('parent_id', 'location_option_id')
    def _check_location_parent(self):
        for account in self:
            level = (account.location_option_id.name or '').strip()
            parent_level = (account.parent_id.location_option_id.name or '').strip()
            if level in ALLOWED_PARENTS and parent_level in LEVELS and parent_level not in ALLOWED_PARENTS[level]:
                raise ValidationError(_(
                    '%(account)s is a %(level)s: its parent must be a %(parents)s, not a %(parent_level)s.',
                    account=account.display_name, level=level,
                    parents=_(' or ').join(ALLOWED_PARENTS[level]), parent_level=parent_level))

    def write(self, vals):
        res = super().write(vals)
        # record rules read the City / Zone of the users' Branch: they are cached
        if {'parent_id', 'location_option_id'} & set(vals):
            self.env.registry.clear_cache()
        return res

    def _compute_product_template_count(self):
        counts = dict(self.env['product.template']._read_group(
            [('analytic_account_id', 'in', self.ids)], ['analytic_account_id'], ['__count']))
        for account in self:
            account.product_template_count = counts.get(account, 0)

    def action_view_products(self):
        """The products of this analytic account (set on each product)."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('product.product_template_action')
        action['domain'] = [('analytic_account_id', '=', self.id)]
        action['context'] = {'default_analytic_account_id': self.id}
        return action

    @api.depends('name')
    def _compute_display_name(self):
        # only the account's own name, not the complete hierarchical path
        for account in self:
            account.display_name = account.name or ''
