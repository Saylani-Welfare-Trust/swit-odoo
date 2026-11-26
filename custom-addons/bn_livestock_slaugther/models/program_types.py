from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    # Master Setup > Livestock Locations: managed there for the whole warehouse
    livestock_inflow_location_id = fields.Many2one(
        'stock.location', string='Livestock Inflow Location',
        compute='_compute_livestock_inflow_location', inverse='_inverse_livestock_inflow_location',
        domain="[('usage', 'in', ('internal', 'transit')), ('warehouse_id', '=', id)]",
        help="Where the livestock lines of this warehouse that do not come from a POS (Import "
             "Donations, API Donations, Direct Deposits) land and wait for slaughter: the Default "
             "Source Location of the warehouse's Livestock Slaughter operation type.")

    def _livestock_type(self):
        """The warehouse's Livestock Slaughter operation type (none created here)."""
        self.ensure_one()
        return self.env['stock.picking.type'].sudo().with_context(active_test=False).search(
            [('warehouse_id', '=', self.id), ('program_type', '=', 'livestock')], limit=1)

    @api.depends('program_picking_type_ids.default_location_src_id', 'program_picking_type_ids.program_type')
    def _compute_livestock_inflow_location(self):
        for warehouse in self:
            warehouse.livestock_inflow_location_id = warehouse._livestock_type().default_location_src_id

    def _inverse_livestock_inflow_location(self):
        for warehouse in self:
            location = warehouse.livestock_inflow_location_id
            if not location:
                raise ValidationError(_("Choose the Livestock Inflow Location of %s.") % warehouse.display_name)
            # the operation type of the program (created when missing), as superuser: the
            # screen is the Inventory Administrators'
            warehouse._program_type('livestock').sudo().default_location_src_id = location

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
