# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Groups that see every city, the same as the "All Cities" record rules of
# bn_donation_box, bn_key_management and bn_rider_shift. Everyone else only sees
# the city of the analytic account on their employee.
ALL_CITIES_GROUPS = (
    'base.group_system',
    'bn_donation_box.donation_box_manager_group',
    'bn_donation_box.donation_box_audit_group',
    'bn_key_management.key_management_manager_group',
    'bn_key_management.key_management_audit_group',
)


class BnCityAccessMixin(models.AbstractModel):
    """City picker of models with a ``city_id`` field: offers only the user's own
    city to users who do not see all cities."""
    _name = 'bn.city.access.mixin'
    _description = 'Donation Box City Access Mixin'

    allowed_city_ids = fields.Many2many(
        'account.analytic.account', string="Allowed Cities", compute='_compute_allowed_city_ids',
        help="Cities the current user may select: only their own city unless they see all cities.")

    @api.model
    def _bn_is_city_restricted(self):
        if self.env.su:
            return False
        user = self.env.user
        return not any(user.has_group(xmlid) for xmlid in ALL_CITIES_GROUPS)

    @api.model
    def _bn_user_city_ids(self):
        """City of the analytic account on the user's employee (the account
        itself or one of its parents)."""
        return self.env['account.analytic.account'].search([
            ('id', 'parent_of', self.env.user.employee_id.analytic_account_id.ids),
            ('location_option_id.name', '=', 'City'),
        ])

    # city_id only makes the first onchange of a new record compute the value
    # (fields without dependencies are left empty there).
    @api.depends('city_id')
    @api.depends_context('uid')
    def _compute_allowed_city_ids(self):
        if self._bn_is_city_restricted():
            cities = self._bn_user_city_ids()
        else:
            cities = self.env['account.analytic.account'].search([('location_option_id.name', '=', 'City')])
        for rec in self:
            rec.allowed_city_ids = cities

    @api.model
    def _bn_check_city(self, city_id):
        """Refuse a city outside the user's own one (the form only offers that one)."""
        if city_id and self._bn_is_city_restricted() and city_id not in self._bn_user_city_ids().ids:
            raise UserError(_('You can only select the city of your own analytic account.'))
