from datetime import date

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestShariahDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        plan = env['account.analytic.plan'].create({'name': 'SD Segment'})
        Account = env['account.analytic.account']
        cls.zakat = Account.create({'name': 'SD Zakat', 'plan_id': plan.id})
        cls.zakat_food = Account.create({'name': 'SD Zakat Food', 'plan_id': plan.id, 'parent_id': cls.zakat.id})
        cls.sadqa = Account.create({'name': 'SD Sadqa', 'plan_id': plan.id})
        Law = env['shariah.law']
        Law.create([
            {'analytic_account_id': cls.zakat.id, 'date': date(2026, 3, 1), 'pos_donation_amount': 100,
             'po_amount': -30},
            {'analytic_account_id': cls.zakat.id, 'date': date(2026, 3, 2), 'api_donation_amount': 50},
            {'analytic_account_id': cls.zakat_food.id, 'date': date(2026, 3, 2), 'dik_amount': 20},
            {'analytic_account_id': cls.sadqa.id, 'date': date(2026, 3, 2), 'pos_donation_amount': 500,
             'welfare_amount': -200},
            {'analytic_account_id': cls.sadqa.id, 'date': date(2026, 5, 1), 'pos_donation_amount': 999},
        ])
        env['shariah.transfer'].create([
            {'date': date(2026, 3, 2), 'source_analytic_account_id': cls.sadqa.id,
             'destination_analytic_account_id': cls.zakat.id, 'amount': 40, 'state': 'posted',
             'is_sync_shariah_law': True},
            {'date': date(2026, 3, 2), 'source_analytic_account_id': cls.zakat.id,
             'destination_analytic_account_id': cls.zakat_food.id, 'amount': 10, 'state': 'posted',
             'is_sync_shariah_law': True},
            {'date': date(2026, 6, 1), 'source_analytic_account_id': cls.sadqa.id,
             'destination_analytic_account_id': cls.zakat.id, 'amount': 7, 'state': 'posted',
             'is_sync_shariah_law': True},
        ])
        group = env.ref('bn_dashboard.group_shariah_dashboard_user')

        def user(login, **vals):
            return env['res.users'].with_context(no_reset_password=True).create(dict({
                'name': login, 'login': login,
                'groups_id': [(6, 0, [env.ref('base.group_user').id, group.id])]}, **vals))
        cls.viewer = user('sd_viewer')
        cls.zakat_viewer = user('sd_zakat', shariah_analytic_ids=[(6, 0, cls.zakat.ids)])
        cls.employee = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'sd_none', 'login': 'sd_none', 'groups_id': [(6, 0, [env.ref('base.group_user').id])]})

    def _data(self, user, analytic=False):
        return self.env['shariah.dashboard'].with_user(user).get_dashboard_data('2026-03-01', '2026-03-31', analytic)

    def test_access(self):
        with self.assertRaises(AccessError):
            self.env['shariah.dashboard'].with_user(self.employee).get_dashboard_data()
        with self.assertRaises(AccessError):
            self._data(self.zakat_viewer, self.sadqa.id)

    def test_segment_with_its_children(self):
        data = self._data(self.viewer, self.zakat.id)
        inflows = {row['label']: row['amount'] for row in data['inflows']}
        self.assertEqual(inflows['POS'], 100)
        self.assertEqual(inflows['DIK'], 20, "Zakat Food is under Zakat")
        self.assertEqual(inflows['Transfers In'], 40, "from Sadqa, in the period; not the June one")
        outflows = {row['label']: row['amount'] for row in data['outflows']}
        self.assertEqual(outflows['Purchase Orders'], 30)
        self.assertEqual(outflows['Transfers Out'], 0, "Zakat to Zakat Food stays inside")
        latest = self.env['shariah.law'].search([('analytic_account_id', '=', self.zakat.id)], order='date desc', limit=1)
        food = self.env['shariah.law'].search([('analytic_account_id', '=', self.zakat_food.id)], limit=1)
        self.assertEqual(data['kpis']['total_closing'], latest.closing_balance + food.closing_balance,
                         "the last balance of each segment")

    def test_all_segments(self):
        data = self._data(self.viewer)
        inflows = {row['label']: row['amount'] for row in data['inflows']}
        self.assertEqual(inflows['POS'], 600, "May is outside the period")
        self.assertEqual(inflows['Transfers In'], 0, "transfers between segments bring nothing in")
        names = {row['name'] for row in data['segments']}
        self.assertTrue({'SD Zakat', 'SD Sadqa'} <= {n.split(' / ')[-1] for n in names})

    def test_allowed_segments(self):
        data = self._data(self.zakat_viewer)
        inflows = {row['label']: row['amount'] for row in data['inflows']}
        self.assertEqual(inflows['POS'], 100, "only Zakat and what is under it")
        self.assertEqual(inflows['Transfers In'], 40)
        segments = self.env['shariah.dashboard'].with_user(self.zakat_viewer).get_segments()
        self.assertNotIn(self.sadqa.id, [s['id'] for s in segments])
        self.assertIn(self.zakat_food.id, [s['id'] for s in segments])
