from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    pos_dd_report_category_ids = fields.Many2many(
        'product.category',
        'pos_dd_report_user_category_rel', 'user_id', 'category_id',
        string='POS+DD Report Categories',
        help="Product categories this user sees on the POS & Direct Deposits report. Empty = all categories.",
    )

    shariah_analytic_ids = fields.Many2many(
        'account.analytic.account',
        relation='res_users_shariah_analytic_rel',
        column1='user_id', column2='account_id',
        string='Shariah Dashboard Segments',
        help="Segments this user can see on the Shariah Dashboard. "
             "Leave empty to see every segment.",
    )

    def _dashboard_locations(self):
        """The analytic accounts the dashboards limit this user to (their Branches /
        Sites and everything under them), and whether the user is unrestricted
        (All Branches / Sites)."""
        self.ensure_one()
        user = self.sudo()
        if user.all_nodes:
            return self.env['account.analytic.account'], True
        return user.node_scope_ids, False
