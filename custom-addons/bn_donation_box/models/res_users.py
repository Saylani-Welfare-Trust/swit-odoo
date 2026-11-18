# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    # The Cities a user works in for the Donation Box records (record rules and
    # City pickers): the City of the analytic account of each location assigned
    # to the user (Allowed Location), and the City of their employee's Branch.
    city_access_ids = fields.Many2many(
        'account.analytic.account', string="Donation Box Cities", compute='_compute_city_access_ids',
        compute_sudo=True,
        help="City of the analytic account of the user's assigned locations, and of their employee's Branch.")

    @api.depends('allowed_location_ids.analytic_account_id.city_id', 'employee_ids.analytic_account_id.city_id')
    def _compute_city_access_ids(self):
        for user in self:
            user.city_access_ids = (user.allowed_location_ids.analytic_account_id.city_id
                                    | user.employee_ids.analytic_account_id.city_id)
