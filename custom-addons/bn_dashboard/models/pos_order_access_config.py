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

    _sql_constraints = [
        ('user_unique', 'unique(user_id)', 'This user already has a POS access configuration.'),
    ]

    # ⚡ NEW: Cascade logic for dropdowns
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

    def _sync_user(self):
        manager = self.env.ref('bn_dashboard.group_pos_order_dashboard_manager').sudo()
        user_grp = self.env.ref('bn_dashboard.group_pos_order_dashboard_user').sudo()
        for rec in self:
            user = rec.user_id.sudo()
            ids = [] if rec.full_access else (rec.province_ids | rec.city_ids | rec.zone_ids).ids
            user.pos_analytic_ids = [(6, 0, ids)]
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
        manager = self.env.ref('bn_dashboard.group_pos_order_dashboard_manager').sudo()
        for u in users.sudo():
            u.pos_analytic_ids = [(5, 0, 0)]
            manager.write({'users': [(3, u.id)]})

    # ------------------------------------------------------------------
    # User access restriction (from pos.order.access.config)
    # ------------------------------------------------------------------
    def _user_pos_accounts(self):
        """
        Return the analytic accounts (incl. descendants) the *current* user
        is allowed to see, per pos.order.access.config / user.pos_analytic_ids.
        Returns an empty recordset if the user is unrestricted.
        """
        user = self.env.user
        if 'pos_analytic_ids' not in user._fields:
            return self.env['account.analytic.account']

        allowed = user.pos_analytic_ids
        if not allowed:
            # No restriction configured -> unrestricted
            return self.env['account.analytic.account']

        # Explicit "All Locations" config -> unrestricted
        if self.env['pos.order.access.config'].sudo().search_count(
                [('user_id', '=', user.id), ('full_access', '=', True)]):
            return self.env['account.analytic.account']

        # Managers are unrestricted
        if user.has_group('bn_dashboard.group_pos_order_dashboard_manager'):
            return self.env['account.analytic.account']

        # Expand to descendants (city -> zones -> branches)
        return self.env['account.analytic.account'].search(
            [('id', 'child_of', allowed.ids)])

    def _get_user_access_domain(self):
        """
        Build an OR-domain that restricts pos.order rows to the accounts
        returned by _user_pos_accounts(). Returns [] when unrestricted.
        """
        accounts = self._user_pos_accounts()
        if not accounts:
            return []

        or_leaves = []
        if 'analytic_account_id' in self._fields:
            or_leaves.append(('analytic_account_id', 'in', accounts.ids))
        if 'session_id' in self._fields:
            or_leaves.append(('session_id.analytic_account_id', 'in', accounts.ids))
        if 'config_id' in self._fields:
            or_leaves.append(('config_id.analytic_account_id', 'in', accounts.ids))
        if 'user_id' in self._fields:
            or_leaves.append(('user_id.employee_id.analytic_account_id', 'in', accounts.ids))
        # Product analytic link (some setups tie city to the product template)
        if 'lines' in self._fields:
            if 'analytic_account_id' in self.env['product.template']._fields:
                or_leaves.append(
                    ('lines.product_id.product_tmpl_id.analytic_account_id', 'in', accounts.ids))
            elif 'analytic_account_ids' in self.env['product.template']._fields:
                or_leaves.append(
                    ('lines.product_id.product_tmpl_id.analytic_account_ids', 'in', accounts.ids))

        if not or_leaves:
            return [('id', '=', 0)]
        if len(or_leaves) == 1:
            return or_leaves

        result = []
        for leaf in or_leaves[:-1]:
            result.extend(['|', leaf])
        result.append(or_leaves[-1])
        return result