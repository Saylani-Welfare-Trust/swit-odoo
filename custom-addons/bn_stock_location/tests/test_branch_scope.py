from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBranchScope(TransactionCase):
    """A user sees the locations of their Branch, its Zone and City (and below
    their own account), on top of the locations set on the user."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        opt = {n: cls.env['location.option'].create({'name': n}) for n in ('City', 'Branch')}
        plan = cls.env['account.analytic.plan'].create({'name': 'Scope Locations'})
        Account = cls.env['account.analytic.account']

        def account(name, level, parent=None):
            return Account.create({'name': name, 'plan_id': plan.id, 'location_option_id': opt[level].id,
                                   'parent_id': parent.id if parent else False})
        cls.city = account('Scope City', 'City')
        cls.branch = account('Scope Branch', 'Branch', cls.city)
        cls.other_city = account('Scope Other City', 'City')
        cls.other_branch = account('Scope Other Branch', 'Branch', cls.other_city)
        cls.warehouse = cls.env['stock.warehouse'].create({'name': 'Scope WH', 'code': 'SCWH'})
        cls.warehouse.view_location_id.analytic_account_id = cls.branch
        Location = cls.env['stock.location']
        cls.city_store = Location.create({'name': 'Scope City Store', 'usage': 'internal',
                                          'analytic_account_id': cls.city.id})
        cls.other_store = Location.create({'name': 'Scope Other Store', 'usage': 'internal',
                                           'analytic_account_id': cls.other_branch.id})
        groups = [cls.env.ref('base.group_user').id, cls.env.ref('stock.group_stock_user').id]
        cls.user = cls.env['res.users'].create({'name': 'Scope User', 'login': 'scope_user',
                                                'groups_id': [(6, 0, groups)]})
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Scope User', 'user_id': cls.user.id, 'cnic_no': '42101-0000010-1',
            'analytic_account_id': cls.branch.id})
        cls.city_user = cls.env['res.users'].create({'name': 'Scope City User', 'login': 'scope_city',
                                                     'groups_id': [(6, 0, groups)]})
        cls.env['hr.employee'].create({'name': 'Scope City User', 'user_id': cls.city_user.id,
                                       'cnic_no': '42101-0000011-1', 'analytic_account_id': cls.city.id})

    def _seen(self, user):
        ids = (self.warehouse.lot_stock_id | self.city_store | self.other_store).ids
        return self.env['stock.location'].with_user(user).search([('id', 'in', ids)])

    def test_branch_user(self):
        self.assertEqual(self._seen(self.user), self.warehouse.lot_stock_id | self.city_store)
        self.assertEqual(self.env['stock.warehouse'].with_user(self.user).search([('code', '=', 'SCWH')]),
                         self.warehouse)

    def test_city_user_sees_its_branches(self):
        self.assertEqual(self._seen(self.city_user), self.warehouse.lot_stock_id | self.city_store)

    def test_moving_the_employee(self):
        self.employee.analytic_account_id = self.other_branch
        self.assertEqual(self._seen(self.user), self.other_store)

    def test_allowed_locations_still_apply(self):
        self.employee.analytic_account_id = False
        self.user.allowed_location_ids = self.other_store
        self.assertEqual(self._seen(self.user), self.other_store)
