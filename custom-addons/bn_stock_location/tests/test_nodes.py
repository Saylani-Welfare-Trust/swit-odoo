from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNodes(TransactionCase):
    """Branch / Site set-up: Province > City > Zone > Branch / Site."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Account = env['account.analytic.account']
        plan = env['account.analytic.plan'].search([('name', '=', 'Location')], limit=1) \
            or env['account.analytic.plan'].create({'name': 'Location'})
        cls.sindh = Account.create({'name': 'N Sindh', 'plan_id': plan.id})
        cls.karachi = Account.create({'name': 'N Karachi', 'plan_id': plan.id, 'parent_id': cls.sindh.id})
        cls.east = Account.create({'name': 'N Zone East', 'plan_id': plan.id, 'parent_id': cls.karachi.id})
        cls.gulshan = Account.create({'name': 'N Gulshan', 'plan_id': plan.id, 'parent_id': cls.east.id})
        cls.johar = Account.create({'name': 'N Johar', 'plan_id': plan.id, 'parent_id': cls.east.id})
        cls.central = Account.create({'name': 'N Karachi Central Store', 'plan_id': plan.id, 'parent_id': cls.karachi.id})
        Warehouse = env['stock.warehouse']
        cls.wh_gulshan = Warehouse.create({'name': 'N WH Gulshan', 'code': 'NWG', 'node_id': cls.gulshan.id})
        cls.wh_gulshan_cold = Warehouse.create({'name': 'N WH Gulshan Cold', 'code': 'NWC', 'node_id': cls.gulshan.id})
        cls.wh_central = Warehouse.create({'name': 'N WH Central', 'code': 'NWX', 'node_id': cls.central.id})
        cls.wh_karachi = Warehouse.create({'name': 'N WH Karachi', 'code': 'NWK', 'node_id': cls.karachi.id})

        def user(login, **vals):
            return env['res.users'].with_context(no_reset_password=True).create(
                dict({'name': login, 'login': login, 'groups_id': [(6, 0, [env.ref('base.group_user').id])]}, **vals))
        cls.city_user = user('n_city', allowed_node_ids=[(6, 0, cls.karachi.ids)])
        cls.branch_user = user('n_branch', allowed_node_ids=[(6, 0, cls.gulshan.ids)])
        cls.branch_store_user = user('n_branch_store', allowed_node_ids=[(6, 0, (cls.johar | cls.central).ids)])
        cls.national_user = user('n_national', all_nodes=True)

    def test_node_warehouse(self):
        with self.assertRaises(UserError):
            self.gulshan._node_warehouse()  # two warehouses, no default: never guessed
        self.gulshan.default_warehouse_id = self.wh_gulshan_cold
        self.assertEqual(self.gulshan._node_warehouse(), self.wh_gulshan_cold)
        self.assertEqual(self.central._node_warehouse(), self.wh_central, "its only warehouse")
        with self.assertRaises(ValidationError):
            self.gulshan.default_warehouse_id = self.wh_central  # not one of its warehouses

    def test_branch_without_warehouse_uses_its_parents(self):
        Warehouse = self.env['stock.warehouse']
        self.assertEqual(Warehouse._warehouse_for_branch(self.johar), self.wh_karachi, "Johar has none: Karachi's")
        self.assertEqual(Warehouse._get_program_type('welfare', branch=self.johar).warehouse_id, self.wh_karachi)
        self.gulshan.default_warehouse_id = self.wh_gulshan
        self.assertEqual(Warehouse._get_program_type('welfare', branch=self.gulshan).warehouse_id, self.wh_gulshan)

    def test_user_scope(self):
        city = self.city_user.node_warehouse_ids
        self.assertEqual(city & (self.wh_gulshan | self.wh_gulshan_cold | self.wh_central | self.wh_karachi),
                         self.wh_gulshan | self.wh_gulshan_cold | self.wh_central | self.wh_karachi)
        self.assertIn(self.johar, self.city_user.node_scope_ids)
        self.assertEqual(self.branch_user.node_warehouse_ids, self.wh_gulshan | self.wh_gulshan_cold)
        self.assertIn(self.wh_gulshan.lot_stock_id, self.branch_user.node_location_ids)
        self.assertNotIn(self.wh_central.lot_stock_id, self.branch_user.node_location_ids)
        self.assertEqual(self.branch_user.node_picking_type_ids.warehouse_id, self.wh_gulshan | self.wh_gulshan_cold)
        self.assertEqual(self.branch_store_user.node_warehouse_ids, self.wh_central, "Johar has none, plus the store")
        self.assertTrue(set((self.wh_gulshan | self.wh_central).ids) <= set(self.national_user.node_warehouse_ids.ids))

    def _old_relation(self, table, column, user, ids):
        """The previous versions' Allowed Locations / Warehouses table (gone on a
        new database; the upgrade reads it before it is dropped)."""
        cr = self.env.cr
        cr.execute('CREATE TABLE IF NOT EXISTS "%s" (res_users_id integer, "%s" integer)' % (table, column))
        for other_id in ids:
            cr.execute('INSERT INTO "%s" (res_users_id, "%s") VALUES (%%s, %%s)' % (table, column), (user.id, other_id))

    def test_fill_from_previous_setup(self):
        Setup = self.env['node.setup']
        untagged = self.env['stock.warehouse'].create({'name': 'N WH Untagged', 'code': 'NWU'})
        untagged.view_location_id.analytic_account_id = self.johar

        def user(login):
            return self.env['res.users'].with_context(no_reset_password=True).create({
                'name': login, 'login': login, 'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})
        located = user('n_located')
        self._old_relation('res_users_stock_location_rel', 'stock_location_id', located,
                           (self.wh_gulshan.lot_stock_id | self.wh_central.lot_stock_id).ids)
        self.wh_gulshan.lot_stock_id.analytic_account_id = self.gulshan
        self.wh_central.lot_stock_id.analytic_account_id = self.central
        # an untagged location counts for its warehouse's Branch / Site
        untagged_user = user('n_untagged')
        self._old_relation('res_users_stock_location_rel', 'stock_location_id', untagged_user,
                           self.wh_karachi.lot_stock_id.ids)
        warehouse_user = user('n_warehouse')
        self._old_relation('res_users_stock_warehouse_rel', 'stock_warehouse_id', warehouse_user,
                           self.wh_central.ids)
        employee_user = user('n_employee')
        self.env['hr.employee'].create({'name': 'n employee', 'user_id': employee_user.id,
                                        'analytic_account_id': self.johar.id})
        stats = Setup._fill()
        self.assertEqual(untagged.node_id, self.johar)
        self.assertEqual(located.allowed_node_ids, self.gulshan | self.central)
        self.assertEqual(untagged_user.allowed_node_ids, self.karachi)
        self.assertEqual(warehouse_user.allowed_node_ids, self.central)
        self.assertEqual(employee_user.allowed_node_ids, self.johar, "the employee's branch")
        self.assertTrue(stats['warehouses'] >= 1)
        # a node under another one of the set adds nothing
        self.assertEqual(Setup._top_nodes(self.karachi | self.gulshan | self.johar), self.karachi)
        # national access for Administrators (and Accounts, Audit, CFO)
        admin = self.env.ref('base.user_admin')
        self.assertTrue(admin.all_nodes)
        # filling again changes nothing already set
        located.allowed_node_ids = self.gulshan
        Setup._fill()
        self.assertEqual(located.allowed_node_ids, self.gulshan)

    def test_report(self):
        html = self.env['node.setup']._report_html()
        self.assertIn('Branches / Sites with several warehouses', html)
        self.assertIn('N Gulshan', html, "Gulshan has two warehouses and no default")
        wizard = self.env['node.setup.wizard'].create({})
        self.assertTrue(wizard.report_html)
        wizard.action_fill()
