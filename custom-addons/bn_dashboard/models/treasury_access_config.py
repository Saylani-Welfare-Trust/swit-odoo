from odoo import api, fields, models


class TreasuryAccessConfig(models.Model):
    _name = 'treasury.access.config'
    _description = 'Treasury Dashboard Access'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade',
                              domain=[('share', '=', False)])
    full_access = fields.Boolean(
        string='All Locations',
        help="Tick to let this user see everything (no restriction).")
    province_ids = fields.Many2many(
        'account.analytic.account',
        relation='treasury_access_province_rel',
        column1='config_id', column2='account_id',
        string='Provinces',
        domain=[('plan_id.name', '=', 'Location'), ('parent_id', '=', False)])
    city_ids = fields.Many2many(
        'account.analytic.account',
        relation='treasury_access_city_rel',
        column1='config_id', column2='account_id',
        string='Cities',
        domain=[('plan_id.name', '=', 'Location'), ('parent_id', '!=', False),
                ('parent_id.parent_id', '=', False)])
    zone_ids = fields.Many2many(
        'account.analytic.account',
        relation='treasury_access_zone_rel',
        column1='config_id', column2='account_id',
        string='Zones',
        domain=[('plan_id.name', '=', 'Location'), ('parent_id.parent_id', '!=', False)])

    _sql_constraints = [
        ('user_unique', 'unique(user_id)', 'This user already has an access configuration.'),
    ]

    # ---- sync to the user (record rules read treasury_analytic_ids) ----
    def _sync_user(self):
        manager = self.env.ref('bn_dashboard.group_treasury_dashboard_manager').sudo()
        user_grp = self.env.ref('bn_dashboard.group_treasury_dashboard_user').sudo()
        for rec in self:
            user = rec.user_id.sudo()
            ids = [] if rec.full_access else (rec.province_ids | rec.city_ids | rec.zone_ids).ids
            user.treasury_analytic_ids = [(6, 0, ids)]
            manager.write({'users': [(4 if rec.full_access else 3, user.id)]})
            user_grp.write({'users': [(4, user.id)]})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_user()
        return recs

    def write(self, vals):
        old_users = self.mapped('user_id')
        res = super().write(vals)
        self._sync_user()
        if 'user_id' in vals:
            self._clear_users(old_users - self.mapped('user_id'))
        return res

    def unlink(self):
        users = self.mapped('user_id')
        res = super().unlink()
        self._clear_users(users)
        return res

    def _clear_users(self, users):
        manager = self.env.ref('bn_dashboard.group_treasury_dashboard_manager').sudo()
        for u in users.sudo():
            u.treasury_analytic_ids = [(5, 0, 0)]
            manager.write({'users': [(3, u.id)]})