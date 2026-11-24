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
            'kitchen': {
                'name': _('Kitchen Production'), 'code': 'mrp_operation', 'sequence_code': 'KIT',
                'src': 'stock', 'dest': 'stock',
            },
        })
        return specs


class StockWarehouseKitchen(models.Model):
    """The kitchen of a warehouse: where its Kitchen Production puts the dishes
    (the ingredients come from its stock)."""
    _inherit = 'stock.warehouse'

    kitchen_location_id = fields.Many2one(
        'stock.location', string='Kitchen Location', check_company=True,
        help="Where this warehouse's kitchen produces. Left empty, its location named Kitchen is used, "
             "or made when first needed.")

    @api.constrains('kitchen_location_id')
    def _check_kitchen_location(self):
        for warehouse in self.filtered('kitchen_location_id'):
            if not self.env['stock.location'].sudo().search_count([
                    ('id', '=', warehouse.kitchen_location_id.id), ('id', 'child_of', warehouse.view_location_id.id)]):
                raise ValidationError(_("%(location)s is not a location of the warehouse %(warehouse)s.",
                                        location=warehouse.kitchen_location_id.display_name,
                                        warehouse=warehouse.display_name))

    def _kitchen_location(self):
        """The kitchen of this warehouse: the one set on it, else its location
        named Kitchen (kept on it), else a new one."""
        self.ensure_one()
        warehouse = self.sudo()
        location = warehouse.kitchen_location_id
        if not location:
            Location = self.env['stock.location'].sudo()
            location = Location.search([('name', '=ilike', 'Kitchen'), ('usage', '=', 'internal'),
                                        ('id', 'child_of', warehouse.view_location_id.id)], order='id', limit=1)
            if not location:
                location = Location.create({'name': 'Kitchen', 'usage': 'internal',
                                            'location_id': warehouse.view_location_id.id,
                                            'company_id': warehouse.company_id.id})
            warehouse.kitchen_location_id = location
        return location.sudo(False)
