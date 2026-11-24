from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRollout(TransactionCase):
    """T7: a province's users are switched to Branch / Site Access after an exact
    preview (a trial switch that is undone), and can be switched back."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        plan = env['account.analytic.plan'].search([('name', '=', 'Location')], limit=1) \
            or env['account.analytic.plan'].create({'name': 'Location'})
        Account = env['account.analytic.account']
        cls.sindh = Account.create({'name': 'RO Sindh', 'plan_id': plan.id})
        cls.karachi = Account.create({'name': 'RO Karachi', 'plan_id': plan.id, 'parent_id': cls.sindh.id})
        cls.gulshan = Account.create({'name': 'RO Gulshan', 'plan_id': plan.id, 'parent_id': cls.karachi.id})
        cls.punjab = Account.create({'name': 'RO Punjab', 'plan_id': plan.id})
        cls.lahore = Account.create({'name': 'RO Lahore', 'plan_id': plan.id, 'parent_id': cls.punjab.id})
        Warehouse = env['stock.warehouse']
        cls.wh_gulshan = Warehouse.create({'name': 'RO WH Gulshan', 'code': 'ROG', 'node_id': cls.gulshan.id})
        cls.wh_lahore = Warehouse.create({'name': 'RO WH Lahore', 'code': 'ROL', 'node_id': cls.lahore.id})
        cls.group = env.ref('bn_stock_location.group_node_access')
        base = [env.ref('base.group_user').id, env.ref('stock.group_stock_user').id]

        def user(login, **vals):
            return env['res.users'].with_context(no_reset_password=True).create(
                dict({'name': login, 'login': login, 'groups_id': [(6, 0, base)]}, **vals))
        # today: allowed the Lahore warehouse by hand; their Branch / Site is Gulshan
        cls.gulshan_user = user('ro_gulshan', allowed_node_ids=[(6, 0, cls.gulshan.ids)],
                                allowed_warehouse_ids=[(6, 0, cls.wh_lahore.ids)])
        cls.lahore_user = user('ro_lahore', allowed_node_ids=[(6, 0, cls.lahore.ids)])
        cls.national = user('ro_national', all_nodes=True)
        cls.no_node = user('ro_no_node')
        env['hr.employee'].create({'name': 'ro no node', 'user_id': cls.no_node.id,
                                   'analytic_account_id': cls.gulshan.id})
        cls.Setup = env['node.setup']

    def test_users_of_a_province(self):
        ready, missing = self.Setup._rollout_users(self.sindh)
        self.assertIn(self.gulshan_user, ready)
        self.assertNotIn(self.lahore_user, ready, "another province")
        self.assertNotIn(self.national, ready, "national users are not limited to a province")
        self.assertIn(self.no_node, missing, "no Branch / Site: listed, not switched")

    def test_preview_changes_nothing(self):
        preview = self.Setup._rollout_preview(self.gulshan_user)
        self.assertEqual(len(preview), 1)
        item = preview[0]
        ours = self.wh_gulshan | self.wh_lahore
        self.assertEqual(item['gains'] & ours, self.wh_gulshan)
        self.assertEqual(item['loses'] & ours, self.wh_lahore)
        for _label, before, after in item['changes']:
            self.assertNotEqual(before, after, "only what changes is listed")
        self.assertFalse(self.gulshan_user.node_access, "the trial switch was undone")
        self.assertIn(self.wh_lahore, self.gulshan_user.scope_warehouse_ids, "the old access is intact")
        html = self.Setup._rollout_html(self.sindh)
        self.assertIn('ro_gulshan', html)

    def test_switch_and_back(self):
        switched = self.Setup._rollout_switch(self.karachi)
        self.assertEqual(switched, self.gulshan_user)
        self.assertTrue(self.gulshan_user.node_access)
        self.assertFalse(self.lahore_user.node_access)
        self.assertEqual(self.gulshan_user.scope_warehouse_ids & (self.wh_gulshan | self.wh_lahore), self.wh_gulshan)
        back = self.Setup._rollout_switch(self.karachi, on=False)
        self.assertEqual(back, self.gulshan_user)
        self.assertFalse(self.gulshan_user.node_access)
        self.assertIn(self.wh_lahore, self.gulshan_user.scope_warehouse_ids)
