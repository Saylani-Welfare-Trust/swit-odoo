from odoo import fields, models




class ResUsers(models.Model):
    _inherit = 'res.users'

    treasury_analytic_ids = fields.Many2many(
        'account.analytic.account',
        'treasury_user_analytic_rel', 'user_id', 'analytic_id',
        string='Allowed Treasury Locations',
        readonly=True,
    )
    pos_analytic_ids = fields.Many2many(
        'account.analytic.account',
        'pos_user_analytic_rel', 'user_id', 'analytic_id',
        string='Allowed POS Locations',
        readonly=True,
    )
    donation_box_analytic_ids = fields.Many2many(
        'account.analytic.account',
        'donation_box_user_analytic_rel', 'user_id', 'analytic_id',
        string='Allowed Donation Box Locations',
        readonly=True,
    )

    # ⚡ NEW — dedicated to the POS & Direct Deposits report
    pos_dd_report_analytic_ids = fields.Many2many(
        'account.analytic.account',
        'pos_dd_report_user_analytic_rel', 'user_id', 'analytic_id',
        string='Allowed POS+DD Report Locations',
        readonly=True,
        help="Managed from Dashboard > Access Configuration (POS & DD Report).",
    )
    pos_dd_report_category_ids = fields.Many2many(
        'product.category',
        'pos_dd_report_user_category_rel', 'user_id', 'category_id',
        string='Allowed POS+DD Report Categories',
        readonly=True,
        help="Empty = all categories.",
    )
    
    livestock_analytic_ids = fields.Many2many(
        'account.analytic.account',
        relation='res_users_livestock_analytic_rel',
        column1='user_id', column2='account_id',
        string='Livestock Dashboard Locations',
        readonly=True,
        help="Locations this user can see on the Livestock Dashboard. "
             "Leave empty to see every location.",
    )

    shariah_analytic_ids = fields.Many2many(
        'account.analytic.account',
        relation='res_users_shariah_analytic_rel',
        column1='user_id', column2='account_id',
        string='Shariah Dashboard Segments',
        help="Segments this user can see on the Shariah Dashboard. "
             "Leave empty to see every segment.",
    )

    def _dashboard_locations(self, field):
        """The analytic accounts a dashboard limits this user to, and whether the
        user is unrestricted.

        - "Branch / Site Access" users (T4/T5): their Branches / Sites and
          everything under them; All Branches / Sites is unrestricted. The
          dashboard's own access list is not used.
        - Other users: the dashboard's access list (``field``); empty is
          unrestricted, as before."""
        self.ensure_one()
        user = self.sudo()
        if 'node_access' in user._fields and user.node_access:
            if user.all_nodes:
                return self.env['account.analytic.account'], True
            return user.node_scope_ids, False
        accounts = user[field]
        return accounts, not accounts
