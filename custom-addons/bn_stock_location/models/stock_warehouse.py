import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    bn_program = fields.Char(
        string='Program', readonly=True, copy=False, index=True,
        help="Set on the operation types created for a program (Welfare, Material "
             "Request ...): every warehouse has its own one, used by that program "
             "instead of the general Receipts / Delivery Orders / Internal Transfers.")


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    bn_program_picking_type_ids = fields.One2many(
        'stock.picking.type', 'warehouse_id', string='Program Operation Types',
        domain=[('bn_program', '!=', False)])

    # ------------------------------------------------------------------
    # Program operation types
    # ------------------------------------------------------------------
    @api.model
    def _bn_program_type_specs(self):
        """{program: spec} - each program module adds its own:

            name, code ('incoming' / 'outgoing' / 'internal' / 'mrp_operation'),
            sequence_code, src, dest

        src / dest: 'stock' (the warehouse stock), 'customer', 'supplier', the
        xml id of a location, or None (set by the document)."""
        return {}

    def _bn_spec_location(self, spec):
        self.ensure_one()
        if not spec:
            return self.env['stock.location']
        if spec == 'stock':
            return self.lot_stock_id
        if spec == 'customer':
            return self.env.ref('stock.stock_location_customers')
        if spec == 'supplier':
            return self.env.ref('stock.stock_location_suppliers')
        return self.env.ref(spec, raise_if_not_found=False) or self.env['stock.location']

    def _bn_program_type(self, program):
        """The operation type of `program` in this warehouse (created if missing)."""
        self.ensure_one()
        PickingType = self.env['stock.picking.type'].sudo().with_context(active_test=False)
        picking_type = PickingType.search([
            ('warehouse_id', '=', self.id), ('bn_program', '=', program)], limit=1)
        if picking_type:
            if not picking_type.active:
                picking_type.active = True
            return picking_type.sudo(False)
        spec = self._bn_program_type_specs().get(program)
        if not spec:
            raise UserError(_('Unknown operation type program "%s".') % program)
        picking_type = PickingType.create({
            'name': spec['name'],
            'code': spec['code'],
            'sequence_code': spec['sequence_code'],
            'warehouse_id': self.id,
            'company_id': self.company_id.id,
            'default_location_src_id': self._bn_spec_location(spec.get('src')).id,
            'default_location_dest_id': self._bn_spec_location(spec.get('dest')).id,
            'bn_program': program,
        })
        _logger.info('Operation type %s created for %s.', picking_type.display_name, self.display_name)
        return picking_type.sudo(False)

    @api.model
    def _bn_warehouse_for(self, location=None, user=None):
        """The warehouse a program document works in: the warehouse of its
        location, else the first allowed warehouse of the user, else the
        company's first warehouse."""
        warehouse = location.warehouse_id if location else self.browse()
        if not warehouse:
            user = user or self.env.user
            company = self.env.company
            if 'allowed_warehouse_ids' in user._fields:
                warehouse = user.sudo().allowed_warehouse_ids.filtered(lambda w: w.company_id == company)[:1]
        if not warehouse:
            warehouse = self.sudo().search([('company_id', '=', self.env.company.id)], limit=1)
        if not warehouse:
            raise UserError(_('No warehouse is configured.'))
        return warehouse

    @api.model
    def _bn_get_program_type(self, program, location=None, user=None):
        return self._bn_warehouse_for(location, user)._bn_program_type(program)

    @api.model
    def _bn_setup_program_types(self):
        """Install / upgrade hook of every program module: each warehouse gets
        the operation types of all installed programs. Idempotent."""
        specs = self._bn_program_type_specs()
        for warehouse in self.sudo().search([]):
            for program in specs:
                warehouse._bn_program_type(program)

    @api.model
    def _bn_archive_legacy_types(self, xmlids):
        """Archive the old global operation types replaced by the per-warehouse
        program types (no warehouse: everybody saw them). Their transfers keep
        them."""
        for xmlid in xmlids:
            picking_type = self.env.ref(xmlid, raise_if_not_found=False)
            if picking_type and picking_type.active and not picking_type.bn_program:
                picking_type.sudo().active = False

    @api.model_create_multi
    def create(self, vals_list):
        warehouses = super().create(vals_list)
        for warehouse in warehouses:
            for program in self._bn_program_type_specs():
                warehouse._bn_program_type(program)
        return warehouses
