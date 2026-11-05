from odoo import models, fields, api

class DashboardConfigurator(models.Model):
    _name = 'dashboard.configurator'
    _description = 'Dashboard Access Configurator'
    _rec_name = 'name'

    name = fields.Char('Rule Name', required=True)
    dashboard_type = fields.Selection([
        ('all', 'All Dashboards'),
        ('treasury', 'Treasury'),
    ], string='Dashboard', required=True, default='treasury')
    
    user_ids = fields.Many2many('res.users', string='Users')
    group_ids = fields.Many2many('res.groups', string='Groups')
    
    allowed_province_ids = fields.Many2many(
        'account.analytic.account', string='Allowed Provinces',
        domain="[('plan_id.name', '=', 'Location'), ('parent_id', '=', False)]"
    )
    allowed_city_ids = fields.Many2many(
        'account.analytic.account', string='Allowed Cities',
        domain="[('plan_id.name', '=', 'Location')]"
    )
    allowed_zone_ids = fields.Many2many(
        'account.analytic.account', string='Allowed Zones',
        domain="[('plan_id.name', '=', 'Location')]"
    )
    allowed_branch_ids = fields.Many2many(
        'account.analytic.account', string='Allowed Branches',
        domain="[('plan_id.name', '=', 'Location')]"
    )

    @api.model
    def get_user_restrictions(self, dashboard_type):
        user = self.env.user
        if user.has_group('base.group_system'):
            return None # Admins see everything

        rule = self.search([
            ('dashboard_type', 'in', ['all', dashboard_type]),
            '|', ('user_ids', 'in', user.id), ('group_ids', 'in', user.groups_id.ids),
        ], limit=1)

        if not rule:
            return None

        analytic_ids = list(set(
            rule.allowed_province_ids.ids +
            rule.allowed_city_ids.ids +
            rule.allowed_zone_ids.ids +
            rule.allowed_branch_ids.ids
        ))

        if not analytic_ids:
            return None # No restriction

        return {
            'analytic_ids': analytic_ids,
            'provinces': rule.allowed_province_ids.ids,
        }