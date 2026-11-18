# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    donation_box_city_ids = fields.Many2many(
        'account.analytic.account', string="Donation Box Cities", compute='_compute_donation_box_city_ids',
        help="Cities of the analytic accounts on the user's Allowed Locations. Locations are tagged "
             "with a Branch (or Zone / City) account, so the City is found by walking up its parents. "
             "Used by the Donation Box record rules.")

    @api.depends('allowed_location_ids.analytic_account_id')
    def _compute_donation_box_city_ids(self):
        Analytic = self.env['account.analytic.account'].sudo()
        for user in self:
            analytic_ids = user.sudo().allowed_location_ids.analytic_account_id.ids
            user.donation_box_city_ids = Analytic.search([
                ('id', 'parent_of', analytic_ids),
                ('location_option_id.name', '=', 'City'),
            ]) if analytic_ids else Analytic
