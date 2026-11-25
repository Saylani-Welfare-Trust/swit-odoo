from odoo import api, fields, models


class ResUsers(models.Model):
    """What a user may see comes from one setting: their Branches / Sites (the
    Location tree: Province > City > Zone > Branch / Site), or All Branches /
    Sites (national). Their warehouses, locations, operation types and analytic
    accounts in scope are computed from it; every record rule reads these."""
    _inherit = 'res.users'

    allowed_product_category_ids = fields.Many2many('product.category', string="Allowed Categories")

    all_nodes = fields.Boolean(
        string='All Branches / Sites (Pakistan)',
        help="National access: every province, city, zone, branch and site "
             "(Administrators, Accounts, Audit, CFO).")
    allowed_node_ids = fields.Many2many(
        'account.analytic.account', 'res_users_allowed_node_rel', 'user_id', 'node_id',
        string='Allowed Branches / Sites',
        help="Any level of the Location tree: a province, city or zone gives everything under it.")
    node_scope_ids = fields.Many2many(
        'account.analytic.account', string='Branches / Sites in Scope', compute='_compute_node_scope',
        compute_sudo=True, help="The allowed nodes and everything under them.")
    node_warehouse_ids = fields.Many2many(
        'stock.warehouse', string='Warehouses (from Branches / Sites)', compute='_compute_node_scope',
        compute_sudo=True)
    node_location_ids = fields.Many2many(
        'stock.location', string='Locations (from Branches / Sites)', compute='_compute_node_scope',
        compute_sudo=True)
    node_picking_type_ids = fields.Many2many(
        'stock.picking.type', string='Operation Types (from Branches / Sites)', compute='_compute_node_scope',
        compute_sudo=True)

    # What the record rules use (every location, warehouse, branch and city rule).
    # National users get everything.
    scope_location_ids = fields.Many2many(
        'stock.location', string="Locations in Scope", compute='_compute_scope', compute_sudo=True,
        help="The locations of the user's Branches / Sites.")
    scope_warehouse_ids = fields.Many2many(
        'stock.warehouse', string="Warehouses in Scope", compute='_compute_scope', compute_sudo=True,
        help="The warehouses of the user's Branches / Sites.")
    scope_analytic_account_ids = fields.Many2many(
        'account.analytic.account', string="Analytic Accounts in Scope",
        compute='_compute_scope', compute_sudo=True,
        help="The user's Branches / Sites and everything under them: records without a location "
             "are matched on these.")

    @api.depends('all_nodes', 'allowed_node_ids')
    @api.depends_context('company')
    def _compute_node_scope(self):
        Account = self.env['account.analytic.account'].sudo()
        Warehouse = self.env['stock.warehouse'].sudo()
        Location = self.env['stock.location'].sudo()
        for user in self:
            if user.all_nodes:
                # national: the whole Location tree and every warehouse
                nodes = Account.search([('plan_id.name', '=', 'Location')])
                warehouses = Warehouse.search([])
            else:
                nodes = Account.search([('id', 'child_of', user.allowed_node_ids.ids)]) if user.allowed_node_ids else Account
                warehouses = Warehouse.search([('node_id', 'in', nodes.ids)]) if nodes else Warehouse
            user.node_scope_ids = nodes
            user.node_warehouse_ids = warehouses
            locations = Location.search([('id', 'child_of', warehouses.view_location_id.ids)]) if warehouses else Location
            if nodes:
                # locations outside any warehouse (e.g. Qurbani city / slaughter points): by their own tag
                tagged = Location.search([('warehouse_id', '=', False), ('analytic_account_id', 'in', nodes.ids)])
                if tagged:
                    locations |= Location.search([('id', 'child_of', tagged.ids)])
            user.node_location_ids = locations
            user.node_picking_type_ids = self.env['stock.picking.type'].sudo().search(
                [('warehouse_id', 'in', warehouses.ids)]) if warehouses else self.env['stock.picking.type']

    @api.depends('all_nodes', 'allowed_node_ids')
    @api.depends_context('company')
    def _compute_scope(self):
        for user in self:
            if user.all_nodes:
                user.scope_location_ids = self.env['stock.location'].sudo().with_context(active_test=False).search(
                    [('usage', 'in', ('internal', 'view'))])
                user.scope_warehouse_ids = self.env['stock.warehouse'].sudo().with_context(active_test=False).search([])
                user.scope_analytic_account_ids = self.env['account.analytic.account'].sudo().with_context(
                    active_test=False).search([])
            else:
                user.scope_location_ids = user.node_location_ids
                user.scope_warehouse_ids = user.node_warehouse_ids
                user.scope_analytic_account_ids = user.node_scope_ids

    def _default_node(self):
        """The Branch / Site a new document of this user belongs to by default:
        their own branch (employee) when it is one of theirs, else their only
        Allowed Branch / Site; several and no own branch: none (chosen)."""
        self.ensure_one()
        user = self.sudo()
        Account = self.env['account.analytic.account']
        branch = user.employee_ids[:1].analytic_account_id
        if branch and (user.all_nodes or branch in user.node_scope_ids):
            return branch.sudo(False)
        if not user.all_nodes and len(user.allowed_node_ids) == 1:
            return user.allowed_node_ids.sudo(False)
        return Account

    @api.model
    def _scope_changed(self):
        """Record rule domains are cached per user, and the users' computed scope
        in the current transaction."""
        self.env.registry.clear_cache()
        self.env['res.users'].invalidate_model()

    def _grant_national(self):
        """Users of the national groups (Administrators, Accounts, Audit, CFO,
        Unrestricted Custom Access) get All Branches / Sites."""
        candidates = self.sudo().filtered(lambda u: not u.share and not u.all_nodes)
        if candidates:
            self.env['node.setup'].sudo()._national_users(candidates).write({'all_nodes': True})

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._grant_national()
        return users

    def write(self, vals):
        res = super().write(vals)
        if any(key == 'groups_id' or key.startswith('in_group_') or key.startswith('sel_groups_') for key in vals):
            self._grant_national()
        if {'all_nodes', 'allowed_node_ids', 'allowed_product_category_ids'} & set(vals):
            self._scope_changed()
        return res


class PosConfigNode(models.Model):
    _inherit = 'pos.config'

    # one warehouse per POS: its orders belong to the warehouse's Branch / Site
    node_id = fields.Many2one(related='warehouse_id.node_id', string='Branch / Site', store=True, index=True)
