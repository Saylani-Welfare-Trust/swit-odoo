from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDashboardNodes(TransactionCase):
    """T5: for "Branch / Site Access" users the dashboards follow their Branches /
    Sites; the dashboards' own access lists apply to the other users only."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        plan = env['account.analytic.plan'].search([('name', '=', 'Location')], limit=1) \
            or env['account.analytic.plan'].create({'name': 'Location'})
        Account = env['account.analytic.account']
        cls.karachi = Account.create({'name': 'DN Karachi', 'plan_id': plan.id})
        cls.gulshan = Account.create({'name': 'DN Gulshan', 'plan_id': plan.id, 'parent_id': cls.karachi.id})
        cls.lahore = Account.create({'name': 'DN Lahore', 'plan_id': plan.id})
        groups = [env.ref('base.group_user').id] + [env.ref('bn_dashboard.%s' % g).id for g in (
            'group_treasury_dashboard_user', 'group_pos_order_dashboard_user', 'group_pos_dd_report_user',
            'group_livestock_dashboard_user', 'group_donation_box_dashboard_user')]
        cls.node_group = env.ref('bn_stock_location.group_node_access')

        def user(login, switched, **vals):
            return env['res.users'].with_context(no_reset_password=True).create(dict({
                'name': login, 'login': login,
                'groups_id': [(6, 0, groups + ([cls.node_group.id] if switched else []))]}, **vals))
        cls.city = user('dn_city', True, allowed_node_ids=[(6, 0, cls.karachi.ids)])
        cls.national = user('dn_national', True, all_nodes=True)
        cls.nothing = user('dn_nothing', True)
        cls.old = user('dn_old', False)
        cls.old.sudo().write({'treasury_analytic_ids': [(6, 0, cls.lahore.ids)],
                              'pos_dd_report_analytic_ids': [(6, 0, cls.lahore.ids)]})

    def test_locations(self):
        accounts, unrestricted = self.city._dashboard_locations('treasury_analytic_ids')
        self.assertFalse(unrestricted)
        self.assertEqual(accounts & (self.karachi | self.gulshan | self.lahore), self.karachi | self.gulshan)
        self.assertEqual(self.national._dashboard_locations('treasury_analytic_ids')[1], True)
        accounts, unrestricted = self.nothing._dashboard_locations('treasury_analytic_ids')
        self.assertFalse(accounts or unrestricted, "no Branch / Site: nothing, not everything")
        self.assertEqual(self.old._dashboard_locations('treasury_analytic_ids'), (self.lahore, False),
                         "not switched: the dashboard's own list")

    def test_rules(self):
        Rule = self.env['ir.rule']
        for user, inside, outside in ((self.city, self.gulshan, self.lahore), (self.old, self.lahore, self.gulshan)):
            domain = str(Rule.with_user(user)._compute_domain('pos.cheque', 'read'))
            self.assertIn(str(inside.id), domain)
        self.assertNotIn(str(self.lahore.id), str(Rule.with_user(self.city)._compute_domain('pos.dd.report', 'read')))
        # a switched user without Branch / Site gets nothing from the report
        Report = self.env['pos.dd.report'].with_user(self.nothing)
        self.assertEqual(Report._get_user_location_domain(), [('analytic_account_id', 'child_of', [])])

    def test_code_filters(self):
        Box = self.env['donation.box.dashboard']
        allowed, visible = Box.with_user(self.city)._get_allowed_location_ids()
        self.assertIn(self.gulshan.id, allowed)
        self.assertNotIn(self.lahore.id, allowed)
        self.assertEqual(Box.with_user(self.national)._get_allowed_location_ids(), (None, None))
        self.assertEqual(Box.with_user(self.nothing)._get_allowed_location_ids(), (set(), set()))
        Order = self.env['pos.order']
        self.assertFalse(Order.with_user(self.national)._user_pos_accounts(), "unrestricted")
        domain = Order.with_user(self.nothing)._get_user_access_domain()
        self.assertTrue(domain, "limited, not unrestricted")
        self.assertTrue(all(leaf[2] == [] for leaf in domain if isinstance(leaf, tuple)), "matches nothing")
        self.assertIn(self.gulshan, Order.with_user(self.city)._user_pos_accounts())
        options = self.env['pos.dd.report'].with_user(self.city).get_location_filter_options()
        self.assertNotIn(self.lahore.id, [c['id'] for c in options['cities']])
