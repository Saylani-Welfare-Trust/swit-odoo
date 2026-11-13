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