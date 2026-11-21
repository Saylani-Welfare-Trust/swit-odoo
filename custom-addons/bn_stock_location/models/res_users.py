from odoo import api, fields, models


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
        """Record rule domains are cached per user."""
        self.env.registry.clear_cache()

    def write(self, vals):
        res = super().write(vals)
        if {'allowed_location_ids', 'allowed_warehouse_ids', 'allowed_product_category_ids'} & set(vals):
            self._scope_changed()
        return res
