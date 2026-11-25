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

    node_id = fields.Many2one(
        'account.analytic.account', string='Branch / Site', index=True,
        help="The node of the Location tree (Province > City > Zone > Branch / Site) this warehouse "
             "belongs to: a branch, or a site of its own (central store, slaughterhouse ...). "
             "Users see it when it is under their Allowed Branches / Sites.")

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
        location = self.env.ref(spec, raise_if_not_found=False) or self.env['stock.location']
        # a location of another company cannot be a default of this warehouse's
        # type (another company's warehouse): the document sets it then
        if location.company_id and location.company_id != self.company_id:
            return self.env['stock.location']
        return location

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
    def _warehouse_for_branch(self, branch):
        """The warehouse of a Branch / Site for a document without a location: the
        node's Default Warehouse or only warehouse, else the closest parent's
        (a branch without a warehouse of its own uses its city's). Until the
        warehouses have their Branch / Site, the location tags are used."""
        if not branch:
            return self.browse()
        branch = branch.sudo()
        chain = self.env['account.analytic.account'].sudo().browse(
            [int(part) for part in reversed((getattr(branch, 'parent_path', '') or '').strip('/').split('/')) if part]) or branch
        company = self.env.company
        if self.sudo().search_count([('node_id', '!=', False), ('company_id', '=', company.id)]):
            for node in chain:
                warehouse = node._node_warehouse()
                if warehouse:
                    return warehouse
            return self.browse()
        warehouses = self.sudo().search([('company_id', '=', company.id)])
        for account in chain:
            found = warehouses.filtered(lambda w: account in (
                w.view_location_id.analytic_account_id | w.lot_stock_id.analytic_account_id))
            if found:
                return found[:1].sudo(False)
        return self.browse()

    @api.model
    def _warehouse_for(self, location=None, user=None, branch=None):
        """The warehouse a program document works in: the warehouse of its
        location, else of its branch, else the user's (of their own Branch /
        Site, else their first warehouse), else the company's first warehouse."""
        warehouse = location.warehouse_id if location else self.browse()
        if not warehouse and branch:
            warehouse = self._warehouse_for_branch(branch)
        if not warehouse:
            user = user or self.env.user
            company = self.env.company
            # the warehouse of the user's own Branch / Site, else their first one
            node = user._default_node()
            if node:
                try:
                    warehouse = self._warehouse_for_branch(node)
                except UserError:
                    warehouse = self.browse()  # several warehouses, no default: below
            if not warehouse and 'scope_warehouse_ids' in user._fields:
                warehouse = user.sudo().scope_warehouse_ids.filtered(lambda w: w.company_id == company)[:1]
        if not warehouse:
            warehouse = self.sudo().search([('company_id', '=', self.env.company.id)], limit=1)
        if not warehouse:
            raise UserError(_('No warehouse is configured.'))
        return warehouse

    @api.model
    def _get_program_type(self, program, location=None, user=None, branch=None):
        """The operation type of `program` in the warehouse of the document: of its
        location, else of its branch (analytic account), else of the user."""
        return self._warehouse_for(location, user, branch)._program_type(program)

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
