from odoo import models, fields, api

class DashboardConfigurator(models.Model):
    _name = 'dashboard.configurator'
    _description = 'Dashboard Access Configurator'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    name = fields.Char('Rule Name', required=True, tracking=True)
    sequence = fields.Integer(default=10, help='Lower = higher priority')
    active = fields.Boolean(default=True, tracking=True)

    dashboard_type = fields.Selection([
        ('all', 'All Dashboards'),
        ('treasury', 'Treasury'),
        ('donation_box', 'Donation Box'),
        ('pos_order', 'POS Order'),
        ('profile', 'Profile Management'),
        ('donation_in_kind', 'Donation In Kind'),
        ('donation_inflow', 'Donation Inflows'),
    ], string='Dashboard', required=True, default='treasury', tracking=True)

    user_ids = fields.Many2many(
        'res.users', 'dash_config_user_rel', 'config_id', 'user_id',
        string='Users'
    )
    group_ids = fields.Many2many(
        'res.groups', 'dash_config_group_rel', 'config_id', 'group_id',
        string='Groups'
    )

    allowed_province_ids = fields.Many2many(
        'account.analytic.account', 'dash_config_prov_rel', 'config_id', 'account_id',
        string='Allowed Provinces',
        domain="[('plan_id.name', '=', 'Location'), ('parent_id', '=', False)]",
    )
    allowed_city_ids = fields.Many2many(
        'account.analytic.account', 'dash_config_city_rel', 'config_id', 'account_id',
        string='Allowed Cities',
    )
    allowed_zone_ids = fields.Many2many(
        'account.analytic.account', 'dash_config_zone_rel', 'config_id', 'account_id',
        string='Allowed Zones',
    )
    allowed_branch_ids = fields.Many2many(
        'account.analytic.account', 'dash_config_branch_rel', 'config_id', 'account_id',
        string='Allowed Branches',
    )
    allowed_segment_l1_ids = fields.Many2many(
        'account.analytic.account', 'dash_config_seg1_rel', 'config_id', 'account_id',
        string='Allowed Segment L1',
        domain="[('plan_id.name', 'ilike', 'Segment'), ('parent_id', '=', False)]",
    )
    allowed_segment_l2_ids = fields.Many2many(
        'account.analytic.account', 'dash_config_seg2_rel', 'config_id', 'account_id',
        string='Allowed Segment L2',
    )

    @api.model
    def get_user_restrictions(self, dashboard_type):
        """Returns the restriction for the current user + dashboard, or None if unrestricted."""
        user = self.env.user

        # System admins see everything
        if user.has_group('base.group_system'):
            return None

        rule = self.search([
            ('active', '=', True),
            '|', ('dashboard_type', '=', 'all'), ('dashboard_type', '=', dashboard_type),
            '|', ('user_ids', 'in', user.id), ('group_ids', 'in', user.groups_id.ids),
        ], order='sequence asc, id asc', limit=1)

        if not rule:
            return None

        analytic_ids = list(set(
            rule.allowed_province_ids.ids
            + rule.allowed_city_ids.ids
            + rule.allowed_zone_ids.ids
            + rule.allowed_branch_ids.ids
            + rule.allowed_segment_l1_ids.ids
            + rule.allowed_segment_l2_ids.ids
        ))

        # If rule exists but no locations/segments set, assume full access
        if not analytic_ids:
            return None

        return {
            'rule_id': rule.id,
            'analytic_ids': analytic_ids,
            'provinces': rule.allowed_province_ids.ids,
            'segment_l1': rule.allowed_segment_l1_ids.ids,
        }