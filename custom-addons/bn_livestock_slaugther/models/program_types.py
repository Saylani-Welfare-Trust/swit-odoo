from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    @api.model
    def _program_type_specs(self):
        """Operation types of this module, one per warehouse
        (see bn_stock_location stock_warehouse.py)."""
        specs = super()._program_type_specs()
        specs.update({
            'livestock': {
                'name': _('Livestock Slaughter'), 'code': 'internal', 'sequence_code': 'LVS',
                'src': 'stock', 'dest': None,
            },
            'livestock_distribution': {
                'name': _('Livestock Distribution'), 'code': 'outgoing', 'sequence_code': 'LVD',
                'src': 'stock', 'dest': 'customer',
            },
        })
        return specs


# the livestock locations of a warehouse: field, name of a new one, names an
# existing location of the warehouse may already have
LIVESTOCK_LOCATIONS = {
    'meat': ('livestock_meat_location_id', 'Meat', ('Meat',)),
    'goat': ('livestock_goat_location_id', 'Goat', ('Goat',)),
    'chicken': ('livestock_chicken_location_id', 'Chicken', ('Chicken',)),
    'cutting': ('livestock_cutting_location_id', 'Livestock Cutting', ('Livestock Cutting',)),
}


class StockWarehouseLivestock(models.Model):
    """Each warehouse has its own department and cutting locations: an animal of
    one Branch / Site never goes into another city's location. Slaughter
    locations are the locations marked "Is Slaughter Location" (there can be
    several): each animal names its own."""
    _inherit = 'stock.warehouse'

    livestock_meat_location_id = fields.Many2one(
        'stock.location', string='Meat Department', check_company=True,
        help="Where a slaughtered animal of the Meat department goes, and the meat products after cutting.")
    livestock_goat_location_id = fields.Many2one(
        'stock.location', string='Goat Department', check_company=True,
        help="Where a slaughtered animal of the Goat department goes, and the other cut products.")
    livestock_chicken_location_id = fields.Many2one(
        'stock.location', string='Chicken Department', check_company=True,
        help="Where a slaughtered animal of the Chicken department goes.")
    livestock_cutting_location_id = fields.Many2one(
        'stock.location', string='Livestock Cutting', check_company=True,
        help="Where an animal is cut and its materials enter.")

    @api.constrains(*[spec[0] for spec in LIVESTOCK_LOCATIONS.values()])
    def _check_livestock_locations(self):
        Location = self.env['stock.location'].sudo()
        for warehouse in self:
            for field, _new, _names in LIVESTOCK_LOCATIONS.values():
                location = warehouse[field]
                if location and not Location.search_count([
                        ('id', '=', location.id), ('id', 'child_of', warehouse.view_location_id.id)]):
                    raise ValidationError(_("%(location)s is not a location of the warehouse %(warehouse)s.",
                                            location=location.display_name, warehouse=warehouse.display_name))

    def _livestock_location(self, kind):
        """The ``kind`` livestock location of this warehouse: the one set on it,
        else its location of that name (kept on it), else a new one."""
        self.ensure_one()
        field, new_name, names = LIVESTOCK_LOCATIONS[kind]
        warehouse = self.sudo()
        location = warehouse[field]
        if not location:
            Location = self.env['stock.location'].sudo()
            for name in names:
                location = Location.search([
                    ('name', '=ilike', name), ('usage', 'in', ('internal', 'transit')),
                    ('id', 'child_of', warehouse.view_location_id.id)], order='id', limit=1)
                if location:
                    break
            if not location:
                location = Location.create({
                    'name': new_name, 'usage': 'transit', 'location_id': warehouse.view_location_id.id,
                    'company_id': warehouse.company_id.id,
                })
            warehouse[field] = location
        return location.sudo(False)


class StockLocationSlaughter(models.Model):
    _inherit = 'stock.location'

    @api.model
    def _slaughter_locations(self, warehouse=None):
        """The slaughter locations (marked "Is Slaughter Location"), of ``warehouse`` when given."""
        domain = [('is_slaughter_location', '=', True), ('usage', 'in', ('internal', 'transit'))]
        if warehouse:
            domain.append(('id', 'child_of', warehouse.view_location_id.id))
        return self.search(domain)
