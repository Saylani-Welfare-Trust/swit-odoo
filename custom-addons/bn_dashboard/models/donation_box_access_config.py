from odoo import api, fields, models

class DonationBoxAccessConfig(models.Model):
    _name = 'donation.box.access.config'
    _description = 'Donation Box Dashboard Access'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade',
                              domain=[('share', '=', False)])
    full_access = fields.Boolean(
        string='All Locations',
        help="Tick to let this user see everything (no restriction).")
    
    province_ids = fields.Many2many(
        'account.analytic.account',
        relation='donation_box_access_province_rel',
        column1='config_id', column2='account_id',
        string='Provinces',
        domain=[('plan_id.name', '=', 'Location'), ('parent_id', '=', False)])
        
    city_ids = fields.Many2many(
        'account.analytic.account',
        relation='donation_box_access_city_rel',
        column1='config_id', column2='account_id',
        string='Cities',
        domain=[('plan_id.name', '=', 'Location'), ('parent_id', '!=', False),
                ('parent_id.parent_id', '=', False)])
                
    zone_ids = fields.Many2many(
        'account.analytic.account',
        relation='donation_box_access_zone_rel',
        column1='config_id', column2='account_id',
        string='Zones',
        domain=[('plan_id.name', '=', 'Location'), ('parent_id.parent_id', '!=', False)])

    _sql_constraints = [
        ('user_unique', 'unique(user_id)', 'This user already has a donation box access configuration.'),
    ]

    # ---- sync to the user ----
    def _sync_user(self):
        for rec in self:
            user = rec.user_id.sudo()
            # If full_access is ticked, clear the restrictions (empty list means full access)
            ids = [] if rec.full_access else (rec.province_ids | rec.city_ids | rec.zone_ids).ids
            user.donation_box_analytic_ids = [(6, 0, ids)]

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_user()
        return recs

    def write(self, vals):
        res = super().write(vals)
        self._sync_user()
        return res

    def unlink(self):
        users = self.mapped('user_id')
        res = super().unlink()
        for u in users:
            u.donation_box_analytic_ids = [(5, 0, 0)]
        return res