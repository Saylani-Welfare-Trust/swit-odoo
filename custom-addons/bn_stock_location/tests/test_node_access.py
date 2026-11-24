from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNodeAccess(TransactionCase):
    """T4: users in "Branch / Site Access" get their access from their Branches /
    Sites; the others keep the location-based access."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        plan = env['account.analytic.plan'].search([('name', '=', 'Location')], limit=1) \
            or env['account.analytic.plan'].create({'name': 'Location'})
        Account = env['account.analytic.account']
        cls.karachi = Account.create({'name': 'NA Karachi', 'plan_id': plan.id})
        cls.gulshan = Account.create({'name': 'NA Gulshan', 'plan_id': plan.id, 'parent_id': cls.karachi.id})
        cls.johar = Account.create({'name': 'NA Johar', 'plan_id': plan.id, 'parent_id': cls.karachi.id})
        cls.lahore = Account.create({'name': 'NA Lahore', 'plan_id': plan.id})
        Warehouse = env['stock.warehouse']
        cls.wh_gulshan = Warehouse.create({'name': 'NA WH Gulshan', 'code': 'NAG', 'node_id': cls.gulshan.id})
        cls.wh_johar = Warehouse.create({'name': 'NA WH Johar', 'code': 'NAJ', 'node_id': cls.johar.id})
        cls.wh_lahore = Warehouse.create({'name': 'NA WH Lahore', 'code': 'NAL', 'node_id': cls.lahore.id})
        cls.point = env['stock.location'].create({'name': 'NA Karachi Slaughter Point', 'usage': 'internal',
                                                  'analytic_account_id': cls.karachi.id})
        cls.group = env.ref('bn_stock_location.group_node_access')
        base = [env.ref('base.group_user').id, env.ref('stock.group_stock_user').id]

        def user(login, switched=True, **vals):
            groups = base + ([cls.group.id] if switched else [])
            return env['res.users'].with_context(no_reset_password=True).create(
                dict({'name': login, 'login': login, 'groups_id': [(6, 0, groups)]}, **vals))
        cls.branch_user = user('na_branch', allowed_node_ids=[(6, 0, cls.gulshan.ids)])
        cls.city_user = user('na_city', allowed_node_ids=[(6, 0, cls.karachi.ids)])
        cls.national = user('na_national', all_nodes=True)
        cls.old_user = user('na_old', switched=False, allowed_warehouse_ids=[(6, 0, cls.wh_lahore.ids)],
                            allowed_node_ids=[(6, 0, cls.gulshan.ids)])
        cls.ours = cls.wh_gulshan | cls.wh_johar | cls.wh_lahore

    def _warehouses(self, user):
        return self.env['stock.warehouse'].with_user(user).search([('id', 'in', self.ours.ids)])

    def test_branch_user(self):
        self.assertTrue(self.branch_user.node_access)
        self.assertEqual(self._warehouses(self.branch_user), self.wh_gulshan)
        self.assertIn(self.gulshan, self.branch_user.scope_analytic_account_ids)
        self.assertNotIn(self.johar, self.branch_user.scope_analytic_account_ids)
        Picking = self.env['stock.picking'].with_user(self.branch_user)
        self.assertFalse(Picking.search([('location_id', '=', self.wh_lahore.lot_stock_id.id)]))

    def test_city_user_sees_its_branches(self):
        self.assertEqual(self._warehouses(self.city_user), self.wh_gulshan | self.wh_johar)
        self.assertIn(self.point, self.city_user.scope_location_ids, "tagged location outside the warehouses")
        self.assertNotIn(self.point, self.branch_user.scope_location_ids)

    def test_national(self):
        self.assertEqual(self._warehouses(self.national), self.ours)

    def test_not_switched_user_keeps_the_old_access(self):
        self.assertFalse(self.old_user.node_access)
        self.assertEqual(self._warehouses(self.old_user), self.wh_lahore, "Allowed Warehouses, not the nodes")

    def test_switch_back(self):
        self.branch_user.groups_id = [(3, self.group.id)]
        self.branch_user.allowed_warehouse_ids = self.wh_lahore
        self.assertEqual(self._warehouses(self.branch_user), self.wh_lahore)
        self.branch_user.groups_id = [(4, self.group.id)]
        self.assertEqual(self._warehouses(self.branch_user), self.wh_gulshan)

    def test_moving_a_warehouse(self):
        self.assertEqual(self._warehouses(self.city_user), self.wh_gulshan | self.wh_johar)
        self.wh_lahore.node_id = self.johar  # cached rules are refreshed
        self.assertEqual(self._warehouses(self.city_user), self.ours)

    # ------------------------------------------------------------------
    # T6: pickers and defaults
    # ------------------------------------------------------------------
    def test_default_node_and_warehouse(self):
        Warehouse = self.env['stock.warehouse']
        self.assertEqual(self.branch_user._default_node(), self.gulshan, "the only Allowed Branch / Site")
        self.assertEqual(Warehouse.with_user(self.branch_user)._warehouse_for(), self.wh_gulshan)
        several = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'na several', 'login': 'na_several',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.group.id])],
            'allowed_node_ids': [(6, 0, (self.gulshan | self.lahore).ids)]})
        self.assertFalse(several._default_node(), "several, no own branch: chosen")
        self.env['hr.employee'].create({'name': 'na several', 'user_id': several.id,
                                        'analytic_account_id': self.lahore.id})
        several.invalidate_recordset()
        self.assertEqual(several._default_node(), self.lahore, "their own branch")
        self.assertEqual(Warehouse.with_user(several)._warehouse_for(), self.wh_lahore)

    def test_branch_picker(self):
        Account = self.env['account.analytic.account'].with_context(branch_scope=True)
        ours = self.karachi | self.gulshan | self.johar | self.lahore
        self.assertEqual(Account.with_user(self.city_user).search([('id', 'in', ours.ids)]),
                         self.karachi | self.gulshan | self.johar)
        self.assertEqual(Account.with_user(self.national).search([('id', 'in', ours.ids)]), ours)
        welfare_field = self.env.registry.get('welfare.line')
        if welfare_field is not None:
            self.assertTrue(self.env['welfare.line']._fields['analytic_account_id'].context.get('branch_scope'))
