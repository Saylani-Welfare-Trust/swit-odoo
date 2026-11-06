from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    treasury_analytic_ids = fields.Many2many(
        'account.analytic.account',
        'treasury_user_analytic_rel', 'user_id', 'analytic_id',
        string='Allowed Treasury Locations',
        readonly=True,
        help="Managed from Dashboard > Access Configuration.",
    )