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
    # For records without a location: their analytic account (Branch) must be
    # the analytic account tagged on one of the user's locations in scope (with
    # their sub-locations and the locations of the warehouses in scope), or the
    # user's own Branch.
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
        Location = self.env['stock.location'].sudo().with_context(active_test=False)
        for user in self:
            roots = user.scope_location_ids | user.scope_warehouse_ids.view_location_id
            accounts = user.sudo().employee_ids.analytic_account_id
            if roots:
                accounts |= Location.search([
                    ('id', 'child_of', roots.ids), ('analytic_account_id', '!=', False),
                ]).analytic_account_id
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
