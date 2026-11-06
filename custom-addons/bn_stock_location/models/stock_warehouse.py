import logging

from odoo.tools.sql import column_exists, rename_column
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    def _auto_init(self):
        # the column of an earlier version keeps each type's program
        if column_exists(self.env.cr, self._table, 'bn_program') \
                and not column_exists(self.env.cr, self._table, 'program_type'):
            rename_column(self.env.cr, self._table, 'bn_program', 'program_type')
        return super()._auto_init()

    program_type = fields.Selection(
        selection='_program_selection', string='Program', copy=False, index=True,
        help="The program (Donation Box, Welfare, Material Request ...) this operation type "
             "is used by in its warehouse. Every warehouse has one per program, created "
             "automatically; an Inventory Administrator can give the program another "
             "operation type of the warehouse instead (Receipt, Delivery, Internal ...).")

    @api.model
    def _program_selection(self):
        specs = self.env['stock.warehouse']._program_type_specs()
        return sorted(((key, str(spec['name'])) for key, spec in specs.items()), key=lambda item: item[1])

    @api.model_create_multi
    def create(self, vals_list):
        types = super().create(vals_list)
        types.filtered('program_type')._release_program()
        return types

    def write(self, vals):
        if 'program_type' in vals and not self.env.su and not self.env.context.get('program_type_sync') \
                and not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('Only Inventory Administrators can change the program of an operation type.'))
        res = super().write(vals)
        if vals.get('program_type') or 'warehouse_id' in vals:
            self.filtered('program_type')._release_program()
        return res

    def _release_program(self):
        """One operation type per program and warehouse: giving a program to a
        type takes it away from the type that had it."""
        for picking_type in self:
            if not picking_type.warehouse_id:
                continue  # bound to its warehouse later (e.g. a historical type)
            others = self.sudo().with_context(active_test=False).search([
                ('id', '!=', picking_type.id),
                ('warehouse_id', '=', picking_type.warehouse_id.id),
                ('program_type', '=', picking_type.program_type),
            ])
            if others:
                others.with_context(program_type_sync=True).write({'program_type': False})
            picking_type.warehouse_id._program_type_changed(picking_type.program_type, picking_type)


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    program_picking_type_ids = fields.One2many(
        'stock.picking.type', 'warehouse_id', string='Program Operation Types',
        domain=[('program_type', '!=', False)])

    def _program_type_changed(self, program, picking_type):
        """Hook: a module keeping the type of its program on the warehouse too
        (Donation Box) follows the change."""

    # ------------------------------------------------------------------
    # Program operation types
    # ------------------------------------------------------------------
    @api.model
    def _program_type_specs(self):
        """{program: spec} - each program module adds its own:

            name, code ('incoming' / 'outgoing' / 'internal' / 'mrp_operation'),
            sequence_code, src, dest; or create_method: a warehouse method
            creating the type itself

        src / dest: 'stock' (the warehouse stock), 'customer', 'supplier', the
        xml id of a location, or None (set by the document)."""
        return {}

    def _spec_location(self, spec):
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

    def _program_type(self, program):
        """The operation type of `program` in this warehouse (created if missing)."""
        self.ensure_one()
        PickingType = self.env['stock.picking.type'].sudo().with_context(active_test=False)
        picking_type = PickingType.search([
            ('warehouse_id', '=', self.id), ('program_type', '=', program)], limit=1)
        if picking_type:
            if not picking_type.active:
                picking_type.active = True
            return picking_type.sudo(False)
        spec = self._program_type_specs().get(program)
        if not spec:
            raise UserError(_('Unknown operation type program "%s".') % program)
        if spec.get('create_method'):
            # the program creates its own type (and locations), e.g. Donation Box
            picking_type = getattr(self, spec['create_method'])()
            picking_type.sudo().with_context(program_type_sync=True).program_type = program
            return picking_type
        picking_type = PickingType.create({
            'name': spec['name'],
            'code': spec['code'],
            'sequence_code': spec['sequence_code'],
            'warehouse_id': self.id,
            'company_id': self.company_id.id,
            'default_location_src_id': self._spec_location(spec.get('src')).id,
            'default_location_dest_id': self._spec_location(spec.get('dest')).id,
            'program_type': program,
        })
        _logger.info('Operation type %s created for %s.', picking_type.display_name, self.display_name)
        return picking_type.sudo(False)

    @api.model
    def _warehouse_for(self, location=None, user=None):
        """The warehouse a program document works in: the warehouse of its
        location, else the first allowed warehouse of the user, else the
        company's first warehouse."""
        warehouse = location.warehouse_id if location else self.browse()
        if not warehouse:
            user = user or self.env.user
            company = self.env.company
            if 'scope_warehouse_ids' in user._fields:
                warehouse = user.sudo().scope_warehouse_ids.filtered(lambda w: w.company_id == company)[:1]
        if not warehouse:
            warehouse = self.sudo().search([('company_id', '=', self.env.company.id)], limit=1)
        if not warehouse:
            raise UserError(_('No warehouse is configured.'))
        return warehouse

    @api.model
    def _get_program_type(self, program, location=None, user=None):
        return self._warehouse_for(location, user)._program_type(program)

    @api.model
    def _setup_program_types(self):
        """Install / upgrade hook of every program module: each warehouse gets
        the operation types of all installed programs. Idempotent."""
        specs = self._program_type_specs()
        for warehouse in self.sudo().search([]):
            for program in specs:
                warehouse._program_type(program)

    @api.model
    def _archive_legacy_types(self, xmlids):
        """Archive the old global operation types replaced by the per-warehouse
        program types (no warehouse: everybody saw them). Their transfers keep
        them."""
        for xmlid in xmlids:
            picking_type = self.env.ref(xmlid, raise_if_not_found=False)
            if picking_type and picking_type.active and not picking_type.program_type:
                picking_type.sudo().active = False

    @api.model_create_multi
    def create(self, vals_list):
        warehouses = super().create(vals_list)
        for warehouse in warehouses:
            for program in self._program_type_specs():
                warehouse._program_type(program)
        return warehouses
