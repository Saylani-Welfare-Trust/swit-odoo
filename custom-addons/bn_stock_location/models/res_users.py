from odoo import api, fields, models

NODE_ACCESS_GROUP = 'bn_stock_location.group_node_access'


class ResUser(models.Model):
    _inherit = 'res.users'

    allowed_location_ids = fields.Many2many('stock.location', string="Allowed Location")
    allowed_warehouse_ids = fields.Many2many('stock.warehouse', string="Allowed Warehouses")
    allowed_product_category_ids = fields.Many2many('product.category', string="Allowed Categories")

    # What the record rules use: the locations / warehouses set above, plus
    # those of the user's analytic line (Branch > Zone > City on the employee):
    # a location whose analytic account is the user's Branch, its Zone or its
    # City, or one below the user's account (a City user sees its branches).
    scope_location_ids = fields.Many2many(
        'stock.location', string="Locations in Scope", compute='_compute_scope', compute_sudo=True,
        help="Allowed locations plus the locations of the user's Branch / Zone / City.")
    scope_warehouse_ids = fields.Many2many(
        'stock.warehouse', string="Warehouses in Scope", compute='_compute_scope', compute_sudo=True,
        help="Allowed warehouses plus the warehouses whose locations are of the user's Branch / Zone / City.")
    # For records without a location: their analytic account (Branch) must be one
    # of these. Each location counts with its own tag only (never the tags of its
    # sub-locations: the City location of a Branch user holds every branch of the
    # city). Going down the hierarchy is only from what is given on purpose: the
    # employee's Branch / Zone / City and the tags of the user's Allowed Locations
    # and Warehouses (a City covers its branches).
    scope_analytic_account_ids = fields.Many2many(
        'account.analytic.account', string="Analytic Accounts in Scope",
        compute='_compute_scope_analytic_accounts', compute_sudo=True,
        help="The analytic accounts tagged on the locations in scope, plus the user's Branch: "
             "records without a location are matched on these.")

    @api.depends('allowed_location_ids', 'allowed_warehouse_ids', 'employee_ids.analytic_account_id')
    @api.depends_context('company')
    def _compute_scope(self):
        Location = self.env['stock.location'].sudo().with_context(active_test=False)
        Warehouse = self.env['stock.warehouse'].sudo().with_context(active_test=False)
        for user in self:
            locations, warehouses = user.allowed_location_ids, user.allowed_warehouse_ids
            accounts = user.sudo().employee_ids.analytic_account_id
            if accounts:
                linked = Location.search([
                    ('usage', 'in', ('internal', 'view')),
                    '|', ('analytic_account_id', 'parent_of', accounts.ids),
                    ('analytic_account_id', 'child_of', accounts.ids)])
                locations |= linked
                warehouses |= Warehouse.search(['|', ('view_location_id', 'in', linked.ids),
                                                ('lot_stock_id', 'in', linked.ids)])
            user.scope_location_ids = locations
            user.scope_warehouse_ids = warehouses

    @api.depends('scope_location_ids', 'scope_warehouse_ids', 'employee_ids.analytic_account_id')
    @api.depends_context('company')
    def _compute_scope_analytic_accounts(self):
        Account = self.env['account.analytic.account'].sudo().with_context(active_test=False)
        for user in self:
            sudo_user = user.sudo()
            assigned = sudo_user.employee_ids.analytic_account_id | (
                sudo_user.allowed_location_ids | sudo_user.allowed_warehouse_ids.view_location_id
                | sudo_user.allowed_warehouse_ids.lot_stock_id).analytic_account_id
            accounts = Account.search([('id', 'child_of', assigned.ids)]) if assigned else Account
            # the locations linked to the Branch (its own, its Zone's and City's): their own tags
            accounts |= (user.scope_location_ids | user.scope_warehouse_ids.view_location_id).analytic_account_id
            user.scope_analytic_account_ids = accounts

    @api.model
    def _scope_changed(self):
        """Record rule domains are cached per user, and the users' computed scope
        in the current transaction."""
        self.env.registry.clear_cache()
        self.env['res.users'].invalidate_model()

    def write(self, vals):
        res = super().write(vals)
        if {'allowed_location_ids', 'allowed_warehouse_ids', 'allowed_product_category_ids'} & set(vals):
            self._scope_changed()
        return res


class ResUsersNodes(models.Model):
    """Branch / Site access (Location tree: Province > City > Zone > Branch / Site).
    One setting per user; their warehouses, locations and operation types are
    computed from it. Not used by the record rules yet (switch-over phase)."""
    _inherit = 'res.users'

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

    @api.depends('all_nodes', 'allowed_node_ids')
    @api.depends_context('company')
    def _compute_node_scope(self):
        Account = self.env['account.analytic.account'].sudo()
        Warehouse = self.env['stock.warehouse'].sudo()
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
            Location = self.env['stock.location'].sudo()
            locations = Location.search([('id', 'child_of', warehouses.view_location_id.ids)]) if warehouses else Location
            if nodes:
                # locations outside any warehouse (e.g. Qurbani city / slaughter points): by their own tag
                tagged = Location.search([('warehouse_id', '=', False), ('analytic_account_id', 'in', nodes.ids)])
                if tagged:
                    locations |= Location.search([('id', 'child_of', tagged.ids)])
            user.node_location_ids = locations
            user.node_picking_type_ids = self.env['stock.picking.type'].sudo().search(
                [('warehouse_id', 'in', warehouses.ids)]) if warehouses else self.env['stock.picking.type']

    def write(self, vals):
        res = super().write(vals)
        if {'all_nodes', 'allowed_node_ids'} & set(vals):
            self._scope_changed()
        return res

    # ------------------------------------------------------------------
    # T4: users in "Branch / Site Access" get their scope from their
    # Branches / Sites. Every location, warehouse, branch and city rule reads
    # these scope fields, so it follows the new basis; the documents' own rule
    # (node_id) is in each module (security/node_rules.xml). Other users keep
    # the location-based scope until they are switched.
    # ------------------------------------------------------------------
    node_access = fields.Boolean(
        string='Branch / Site Access', compute='_compute_node_access',
        help="The user's access comes from their Branches / Sites (group Branch / Site Access).")

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

    @api.depends('groups_id')
    def _compute_node_access(self):
        group = self.env.ref(NODE_ACCESS_GROUP, raise_if_not_found=False)
        for user in self:
            user.node_access = bool(group) and group in user.sudo().groups_id

    @api.depends('allowed_location_ids', 'allowed_warehouse_ids', 'employee_ids.analytic_account_id',
                 'groups_id', 'all_nodes', 'allowed_node_ids')
    @api.depends_context('company')
    def _compute_scope(self):
        switched = self.filtered('node_access')
        super(ResUsersNodes, self - switched)._compute_scope()
        for user in switched:
            if user.all_nodes:
                user.scope_location_ids = self.env['stock.location'].sudo().with_context(active_test=False).search(
                    [('usage', 'in', ('internal', 'view'))])
                user.scope_warehouse_ids = self.env['stock.warehouse'].sudo().with_context(active_test=False).search([])
            else:
                user.scope_location_ids = user.node_location_ids
                user.scope_warehouse_ids = user.node_warehouse_ids

    @api.depends('scope_location_ids', 'scope_warehouse_ids', 'employee_ids.analytic_account_id',
                 'groups_id', 'all_nodes', 'allowed_node_ids')
    @api.depends_context('company')
    def _compute_scope_analytic_accounts(self):
        switched = self.filtered('node_access')
        super(ResUsersNodes, self - switched)._compute_scope_analytic_accounts()
        for user in switched:
            if user.all_nodes:
                user.scope_analytic_account_ids = self.env['account.analytic.account'].sudo().with_context(
                    active_test=False).search([])
            else:
                user.scope_analytic_account_ids = user.node_scope_ids


class PosConfigNode(models.Model):
    _inherit = 'pos.config'

    # one warehouse per POS: its orders belong to the warehouse's Branch / Site
    node_id = fields.Many2one(related='warehouse_id.node_id', string='Branch / Site', store=True, index=True)
