from odoo import api, fields, models

class PosOrderAccessConfig(models.Model):
    _name = 'pos.order.access.config'
    _description = 'POS Order Dashboard Access'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade',
                              domain=[('share', '=', False)])
    full_access = fields.Boolean(
        string='All Locations',
        help="Tick to let this user see everything (no restriction).")
    province_ids = fields.Many2many(
        'account.analytic.account',
        relation='pos_access_province_rel',
        column1='config_id', column2='account_id',
        string='Provinces',
        domain=[('plan_id.name', '=', 'Location'), ('parent_id', '=', False)])
    city_ids = fields.Many2many(
        'account.analytic.account',
        relation='pos_access_city_rel',
        column1='config_id', column2='account_id',
        string='Cities',
        domain=[('plan_id.name', '=', 'Location'), ('parent_id', '!=', False),
                ('parent_id.parent_id', '=', False)])
    zone_ids = fields.Many2many(
        'account.analytic.account',
        relation='pos_access_zone_rel',
        column1='config_id', column2='account_id',
        string='Zones',
        domain=[('plan_id.name', '=', 'Location'), ('parent_id.parent_id', '!=', False)])
    
    # Points of sale: the user also sees the branch (analytic account) of each
    shop_ids = fields.Many2many(
        'pos.config',
        relation='pos_access_shop_rel',
        column1='config_id', column2='shop_id',
        string='Branches / Shops',
        help="Points of sale whose branch this user can also report on.")

    _sql_constraints = [
        ('user_unique', 'unique(user_id)', 'This user already has a POS access configuration.'),
    ]

    @api.onchange('province_ids')
    def _onchange_province_ids(self):
        if self.province_ids:
            return {'domain': {'city_ids': [('parent_id', 'in', self.province_ids.ids)]}}
        return {'domain': {'city_ids': [('plan_id.name', '=', 'Location'), ('parent_id', '!=', False), ('parent_id.parent_id', '=', False)]}}

    @api.onchange('city_ids')
    def _onchange_city_ids(self):
        if self.city_ids:
            return {'domain': {'zone_ids': [('parent_id', 'in', self.city_ids.ids)]}}
        return {'domain': {'zone_ids': [('plan_id.name', '=', 'Location'), ('parent_id.parent_id', '!=', False)]}}

    # Points of sale offered: those under the selected Zones / Cities / Provinces
    @api.onchange('province_ids', 'city_ids', 'zone_ids')
    def _onchange_location_for_shops(self):
        domain = [('analytic_account_id', '!=', False)]
        if self.zone_ids:
            domain = [('analytic_account_id', 'child_of', self.zone_ids.ids)]
        elif self.city_ids:
            domain = [('analytic_account_id', 'child_of', self.city_ids.ids)]
        elif self.province_ids:
            domain = [('analytic_account_id', 'child_of', self.province_ids.ids)]
        return {'domain': {'shop_ids': domain}}

    def _sync_user(self):
        user_grp = self.env.ref('bn_dashboard.group_pos_order_dashboard_user').sudo()
        # report_grp = self.env.ref('bn_dashboard.group_pos_dd_report_user').sudo()

        for rec in self:
            user = rec.user_id.sudo()
            if rec.full_access:
                ids = []
            else:
                # Combine analytic IDs from locations and the analytic accounts of selected shops
                shop_analytic_ids = rec.shop_ids.mapped('analytic_account_id').ids
                ids = list(set((rec.province_ids | rec.city_ids | rec.zone_ids).ids + shop_analytic_ids))
                
            user.pos_analytic_ids = [(6, 0, ids)]
            user_grp.write({'users': [(4, user.id)]})
            # report_grp.write({'users': [(4, user.id)]})

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
        user_grp = self.env.ref('bn_dashboard.group_pos_order_dashboard_user').sudo()
        for u in users.sudo():
            u.pos_analytic_ids = [(5, 0, 0)]
            user_grp.write({'users': [(3, u.id)]})