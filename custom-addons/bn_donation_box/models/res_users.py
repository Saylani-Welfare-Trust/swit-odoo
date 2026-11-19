# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    # The Cities a user works in for the Donation Box records (record rules and
    # City pickers): the City of each analytic account in the user's scope
    # (res.users.scope_analytic_account_ids of bn_stock_location: the accounts of
    # their Allowed Locations with sub-locations, Allowed Warehouses and the
    # locations of their Branch / Zone / City, plus their employee's Branch).
    # Matched at City level, unlike the Branch-level rules of the other modules.
    city_access_ids = fields.Many2many(
        'account.analytic.account', string="Donation Box Cities", compute='_compute_city_access_ids',
        compute_sudo=True,
        help="City of each analytic account in the user's scope (locations, warehouses and employee's Branch).")

    @api.depends('scope_analytic_account_ids')
    @api.depends_context('company')
    def _compute_city_access_ids(self):
        for user in self:
            user.city_access_ids = user.scope_analytic_account_ids.city_id
