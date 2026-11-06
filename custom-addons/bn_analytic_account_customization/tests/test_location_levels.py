from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLocationLevels(TransactionCase):
    """City > Zone > Branch on analytic accounts and employees; products carry
    their analytic account."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        LO = cls.env['location.option']
        cls.opt = {n: LO.create({'name': n}) for n in ('City', 'Zone', 'Branch')}
        cls.plan = cls.env['account.analytic.plan'].create({'name': 'Locations'})
        cls.city = cls._account('City K', 'City')
        cls.city2 = cls._account('City L', 'City')
        cls.zone = cls._account('Zone 1', 'Zone', cls.city)
        cls.branch = cls._account('Branch 1', 'Branch', cls.zone)

    @classmethod
    def _account(cls, name, level, parent=None):
        return cls.env['account.analytic.account'].create({
            'name': name, 'plan_id': cls.plan.id, 'location_option_id': cls.opt[level].id,
            'parent_id': parent.id if parent else False})

    def test_levels(self):
        self.assertEqual((self.branch.zone_id, self.branch.city_id), (self.zone, self.city))
        self.assertEqual((self.zone.zone_id, self.zone.city_id), (self.zone, self.city))
        self.assertFalse(self.city.zone_id)
        direct = self._account('Branch 2', 'Branch', self.city)
        self.assertFalse(direct.zone_id)
        self.assertEqual(direct.city_id, self.city)

    def test_moving_a_zone_moves_its_branches(self):
        self.zone.parent_id = self.city2
        self.assertEqual(self.branch.city_id, self.city2)

    def test_wrong_parent_refused(self):
        with self.assertRaises(ValidationError):
            self._account('Zone under branch', 'Zone', self.branch)
        with self.assertRaises(ValidationError):
            self._account('Branch under branch', 'Branch', self.branch)

    def test_employee_levels(self):
        employee = self.env['hr.employee'].create({
            'name': 'Levels', 'cnic_no': '42101-0000009-1', 'analytic_account_id': self.branch.id})
        self.assertEqual((employee.zone_id, employee.city_id), (self.zone, self.city))
        self.env.flush_all()
        public = self.env['hr.employee.public'].browse(employee.id)
        self.assertEqual(public.city_id, self.city)

    def test_product_analytic_account(self):
        template = self.env['product.template'].create({'name': 'Zakat', 'analytic_account_id': self.branch.id})
        self.assertEqual(template.product_variant_id.analytic_account_id, self.branch)
        self.assertEqual(self.branch.product_template_count, 1)
        action = self.branch.action_view_products()
        self.assertEqual(self.env['product.template'].search(action['domain']), template)
        template.product_variant_id.analytic_account_id = self.zone
        self.assertEqual(template.analytic_account_id, self.zone)
        Account = self.env['account.analytic.account']
        self.assertNotIn('product_ids', Account._fields)
        self.assertNotIn('product_template_ids', Account._fields)
