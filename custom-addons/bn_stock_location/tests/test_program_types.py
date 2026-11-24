from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProgramTypes(TransactionCase):
    """Each program has its own operation type in every warehouse, and a document
    gets the one of its own warehouse (location, else branch, else the user)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Account = env['account.analytic.account']
        plan = env['account.analytic.plan'].search([('name', '=', 'Location')], limit=1) \
            or env['account.analytic.plan'].create({'name': 'Location'})
        cls.city = Account.create({'name': 'Prog City', 'plan_id': plan.id})
        cls.branch_a = Account.create({'name': 'Prog Branch A', 'plan_id': plan.id, 'parent_id': cls.city.id})
        cls.branch_b = Account.create({'name': 'Prog Branch B', 'plan_id': plan.id, 'parent_id': cls.city.id})
        cls.branch_c = Account.create({'name': 'Prog Branch C', 'plan_id': plan.id, 'parent_id': cls.city.id})
        Warehouse = env['stock.warehouse']
        cls.wh_a = Warehouse.create({'name': 'Prog WH A', 'code': 'PWA'})
        cls.wh_b = Warehouse.create({'name': 'Prog WH B', 'code': 'PWB'})
        cls.wh_a.view_location_id.analytic_account_id = cls.branch_a
        cls.wh_b.lot_stock_id.analytic_account_id = cls.branch_b

    def test_every_warehouse_has_every_program_type(self):
        programs = set(self.env['stock.warehouse']._program_type_specs())
        for warehouse in self.wh_a | self.wh_b:
            types = self.env['stock.picking.type'].search(
                [('warehouse_id', '=', warehouse.id), ('program_type', '!=', False)])
            self.assertEqual(set(types.mapped('program_type')), programs, warehouse.name)

    def test_type_of_the_location_warehouse(self):
        Warehouse = self.env['stock.warehouse']
        for program in Warehouse._program_type_specs():
            picking_type = Warehouse._get_program_type(program, self.wh_b.lot_stock_id)
            self.assertEqual(picking_type.warehouse_id, self.wh_b, program)
            self.assertEqual(picking_type.program_type, program)

    def test_type_of_the_branch_warehouse(self):
        Warehouse = self.env['stock.warehouse']
        self.assertEqual(Warehouse._get_program_type('welfare', branch=self.branch_a).warehouse_id, self.wh_a)
        self.assertEqual(Warehouse._get_program_type('welfare', branch=self.branch_b).warehouse_id, self.wh_b)
        # the location wins over the branch
        self.assertEqual(Warehouse._get_program_type(
            'welfare', location=self.wh_a.lot_stock_id, branch=self.branch_b).warehouse_id, self.wh_a)

    def test_branch_without_warehouse_uses_its_city(self):
        Warehouse = self.env['stock.warehouse']
        self.wh_a.view_location_id.analytic_account_id = self.city
        self.assertEqual(Warehouse._warehouse_for_branch(self.branch_c), self.wh_a)

    def test_program_moved_to_another_type(self):
        """An Inventory Administrator gives the program another type of the warehouse:
        documents use that one, the old type loses the program."""
        Warehouse = self.env['stock.warehouse']
        old = Warehouse._get_program_type('welfare', self.wh_a.lot_stock_id)
        self.wh_a.out_type_id.program_type = 'welfare'
        self.assertEqual(Warehouse._get_program_type('welfare', self.wh_a.lot_stock_id), self.wh_a.out_type_id)
        self.assertFalse(old.program_type)
