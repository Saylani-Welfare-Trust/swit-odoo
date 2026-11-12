from odoo import api, fields, models


class PosDdReportAccessConfig(models.Model):
    _name = 'pos.dd.report.access.config'
    _description = 'POS & Direct Deposits Report Access'
    _rec_name = 'user_id'

    user_id = fields.Many2one(
        'res.users', required=True, ondelete='cascade',
        domain=[('share', '=', False)])

    full_access = fields.Boolean(
        string='All Locations & Categories',
        help="Tick to give this user unrestricted access to the report "
             "(no location and no category restriction).")

    # ---- Location restriction ----
    province_ids = fields.Many2many(
        'account.analytic.account',
        relation='pos_dd_report_province_rel',
        column1='config_id', column2='account_id',
        string='Provinces',
        domain=[('plan_id.name', '=', 'Location'), ('parent_id', '=', False)])

    city_ids = fields.Many2many(
        'account.analytic.account',
        relation='pos_dd_report_city_rel',
        column1='config_id', column2='account_id',
        string='Cities',
        domain=[('plan_id.name', '=', 'Location'), ('parent_id', '!=', False),
                ('parent_id.parent_id', '=', False)])

    zone_ids = fields.Many2many(
        'account.analytic.account',
        relation='pos_dd_report_zone_rel',
        column1='config_id', column2='account_id',
        string='Zones',
        domain=[('plan_id.name', '=', 'Location'), ('parent_id.parent_id', '!=', False)])

    # ---- Product category restriction ----
    category_ids = fields.Many2many(
        'product.category',
        relation='pos_dd_report_category_rel',
        column1='config_id', column2='category_id',
        string='Allowed Product Categories',
        help="Restrict the report to these product categories "
             "(child categories are included). "
             "Leave empty to show all categories.")

    _sql_constraints = [
        ('user_unique', 'unique(user_id)',
         'This user already has a POS & DD report access configuration.'),
    ]

    # ---- cascade onchange ----
    @api.onchange('province_ids')
    def _onchange_province_ids(self):
        if self.province_ids:
            return {'domain': {'city_ids': [('parent_id', 'in', self.province_ids.ids)]}}
        return {'domain': {'city_ids': [('plan_id.name', '=', 'Location'),
                                        ('parent_id', '!=', False),
                                        ('parent_id.parent_id', '=', False)]}}

    @api.onchange('city_ids')
    def _onchange_city_ids(self):
        if self.city_ids:
            return {'domain': {'zone_ids': [('parent_id', 'in', self.city_ids.ids)]}}
        return {'domain': {'zone_ids': [('plan_id.name', '=', 'Location'),
                                        ('parent_id.parent_id', '!=', False)]}}

    # ---- sync to the user ----
    def _sync_user(self):
        report_grp = self.env.ref('bn_dashboard.group_pos_dd_report_user').sudo()

        for rec in self:
            user = rec.user_id.sudo()

            loc_ids = [] if rec.full_access else (
                rec.province_ids | rec.city_ids | rec.zone_ids).ids
            user.pos_dd_report_analytic_ids = [(6, 0, loc_ids)]

            # Empty list = no category restriction
            user.pos_dd_report_category_ids = [(6, 0, rec.category_ids.ids)]

            report_grp.write({'users': [(4, user.id)]})

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
        report_grp = self.env.ref('bn_dashboard.group_pos_dd_report_user').sudo()
        for u in users.sudo():
            u.pos_dd_report_analytic_ids = [(5, 0, 0)]
            u.pos_dd_report_category_ids = [(5, 0, 0)]
            report_grp.write({'users': [(3, u.id)]})