from odoo import models, fields, api

class TreasuryDashboardConfigurator(models.Model):
    _name = 'treasury.dashboard.configurator'
    _description = 'Treasury Dashboard Configurator'
    _rec_name = 'name'

    name = fields.Char('Rule Name', required=True)
    user_ids = fields.Many2many('res.users', string='Users')
    group_ids = fields.Many2many('res.groups', string='Groups')

    # ⚡ FIX: Explicitly define the relation table and columns for each M2M field
    allowed_province_ids = fields.Many2many(
        'account.analytic.account', 
        'treasury_cfg_prov_rel', 'config_id', 'account_id',
        string='Allowed Provinces',
        domain="[('plan_id.name', '=', 'Location'), ('parent_id', '=', False)]"
    )
    allowed_city_ids = fields.Many2many(
        'account.analytic.account', 
        'treasury_cfg_city_rel', 'config_id', 'account_id',
        string='Allowed Cities',
    )
    allowed_zone_ids = fields.Many2many(
        'account.analytic.account', 
        'treasury_cfg_zone_rel', 'config_id', 'account_id',
        string='Allowed Zones',
    )
    allowed_branch_ids = fields.Many2many(
        'account.analytic.account', 
        'treasury_cfg_branch_rel', 'config_id', 'account_id',
        string='Allowed Branches',
    )

    @api.model
    def get_user_restriction(self):
        user = self.env.user
        # System admins see everything
        if user.has_group('base.group_system'):
            return None

        rule = self.search([
            '|', ('user_ids', 'in', user.id), ('group_ids', 'in', user.groups_ids.ids)
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
            return None

        return {
            'analytic_ids': analytic_ids,
            'provinces': rule.allowed_province_ids.ids,
        }