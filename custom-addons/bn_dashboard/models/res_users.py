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
    pos_analytic_ids = fields.Many2many(
        'account.analytic.account',
        'pos_user_analytic_rel', 'user_id', 'analytic_id',
        string='Allowed POS Locations',
        readonly=True,
        help="Managed from Dashboard > Access Configuration.",
    )
    donation_box_analytic_ids = fields.Many2many(
        'account.analytic.account',
        'donation_box_user_analytic_rel', 'user_id', 'analytic_id',
        string='Allowed Donation Box Locations',
        readonly=True,
        help="Managed from Donation Box > Access Configuration. "
             "Assigning a province/city auto-includes all descendants.",
    )