from odoo import api, fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    # The Branch (or Zone / City) the location belongs to: its users see it
    # (res.users.scope_location_ids).
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")
    location_option_id = fields.Many2one('location.option', string="Location Option")

    # Roles of a location: a warehouse may hold several locations of each role;
    # each document chooses its own (filled when its warehouse has only one).
    is_slaughter_location = fields.Boolean('Is Slaughter Location')
    is_distribution_location = fields.Boolean('Is Distribution Location')
    is_meat_location = fields.Boolean('Is Meat Location', help="Livestock: Meat department / meat products after cutting.")
    is_goat_location = fields.Boolean('Is Goat Location', help="Livestock: Goat department / other cut products.")
    is_chicken_location = fields.Boolean('Is Chicken Location', help="Livestock: Chicken department.")
    is_cutting_location = fields.Boolean('Is Cutting Location', help="Livestock: where animals are cut.")
    is_kitchen_location = fields.Boolean('Is Kitchen Location', help="Kitchen: where the kitchen produces.")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if any(vals.get('analytic_account_id') for vals in vals_list):
            self.env['res.users']._scope_changed()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'analytic_account_id' in vals:
            self.env['res.users']._scope_changed()
        return res

    @api.model
    def _role_locations(self, role, warehouse=None):
        """The locations marked with ``role`` (e.g. 'is_cutting_location'), of
        ``warehouse`` when given."""
        domain = [(role, '=', True), ('usage', 'in', ('internal', 'transit'))]
        if warehouse:
            domain.append(('id', 'child_of', warehouse.view_location_id.id))
        return self.search(domain)

    @api.model
    def _single_role_location(self, role, warehouse):
        """The only ``role`` location of ``warehouse`` (several or none: empty,
        the document's user chooses)."""
        if not warehouse:
            return self.browse()
        locations = self.sudo()._role_locations(role, warehouse)
        return locations.sudo(False) if len(locations) == 1 else self.browse()
