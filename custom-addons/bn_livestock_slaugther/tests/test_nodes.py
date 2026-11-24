from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLivestockNodes(TransactionCase):
    """Documents carry their Branch / Site; livestock uses the locations of its
    own warehouse, never the first location of a name."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Plan = env['account.analytic.plan']
        cls.plan = Plan.search([('name', '=', 'Location')], limit=1) or Plan.create({'name': 'Location'})
        cls.segment_plan = Plan.create({'name': 'LN Segment'})
        Account = env['account.analytic.account']
        cls.karachi = Account.create({'name': 'LN Karachi', 'plan_id': cls.plan.id})
        cls.gulshan = Account.create({'name': 'LN Gulshan', 'plan_id': cls.plan.id, 'parent_id': cls.karachi.id})
        cls.lahore = Account.create({'name': 'LN Lahore', 'plan_id': cls.plan.id})
        cls.segment = Account.create({'name': 'LN Livestock Segment', 'plan_id': cls.segment_plan.id})
        Warehouse = env['stock.warehouse']
        cls.wh_karachi = Warehouse.create({'name': 'LN WH Karachi', 'code': 'LNK', 'node_id': cls.gulshan.id})
        cls.wh_lahore = Warehouse.create({'name': 'LN WH Lahore', 'code': 'LNL', 'node_id': cls.lahore.id})
        cls.product = env['product.product'].create({'name': 'LN Goat', 'type': 'product'})
        Location = env['stock.location']
        cls.karachi_slaughter = Location.create({'name': 'LN Karachi Slaughter', 'usage': 'internal',
                                                 'location_id': cls.wh_karachi.view_location_id.id,
                                                 'is_slaughter_location': True})
        cls.lahore_slaughter = Location.create({'name': 'LN Lahore Slaughter', 'usage': 'internal',
                                                'location_id': cls.wh_lahore.view_location_id.id,
                                                'is_slaughter_location': True})
        cls.manager = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ln manager', 'login': 'ln_manager',
            'groups_id': [(6, 0, [env.ref('base.group_user').id, env.ref('stock.group_stock_manager').id,
                                  env.ref('bn_livestock_slaugther.livestock_slaugther_menu_group').id,
                                  env.ref('bn_livestock_slaugther.livestock_slaugther_admin_group').id,
                                  env.ref('bn_stock_location.stock_scope_unrestricted_group').id])]})
        env['hr.employee'].create({'name': 'ln manager', 'user_id': cls.manager.id,
                                   'analytic_account_id': cls.lahore.id})

    # ------------------------------------------------------------------
    # Branch / Site of a document
    # ------------------------------------------------------------------
    def test_node_from_location(self):
        requisition = self.env['livestock.requisition'].create({
            'destination_location_id': self.wh_karachi.lot_stock_id.id,
            'source_location_id': self.wh_lahore.lot_stock_id.id,
        })
        self.assertEqual(requisition.node_id, self.gulshan, "the destination's warehouse comes first")
        requisition.destination_location_id = False
        self.assertEqual(requisition.node_id, self.lahore, "then the source's")

    def test_node_of_location_outside_warehouses(self):
        parent = self.env['stock.location'].create({'name': 'LN Qurbani City', 'usage': 'view',
                                                    'analytic_account_id': self.karachi.id})
        child = self.env['stock.location'].create({'name': 'LN Slaughter Point', 'usage': 'internal',
                                                   'location_id': parent.id})
        meat = self.env['livestock.meat.management'].create({'location_id': child.id})
        self.assertEqual(meat.node_id, self.karachi, "no warehouse: the closest tag up the locations")

    def test_segment_is_never_a_node(self):
        Mixin = self.env['node.document.mixin']
        self.assertFalse(Mixin._node_of(self.segment))
        self.assertEqual(Mixin._node_of(self.gulshan), self.gulshan)

    def test_node_from_creator(self):
        cutting = self.env['livestock.cutting'].with_user(self.manager).create({
            'product_id': self.product.id, 'slaughter_location_id': self.lahore_slaughter.id})
        self.assertEqual(cutting.warehouse_id, self.wh_lahore, "the user's Branch / Site warehouse")
        self.assertEqual(cutting.node_id, self.lahore)
        cutting.with_user(self.manager).action_validate_picking()
        Quant = self.env['stock.quant']
        self.assertEqual(Quant._get_available_quantity(self.product, self.wh_lahore.livestock_cutting_location_id), 1,
                         "from its slaughter location into the warehouse's Cutting location")
        self.assertEqual(Quant._get_available_quantity(self.product, self.lahore_slaughter, allow_negative=True), -1)
        center = self.env['distribution.center'].with_user(self.manager).create({})
        self.assertEqual(center.node_id, self.lahore, "no source: the creator's Branch / Site")

    def test_update_documents(self):
        requisition = self.env['livestock.requisition'].create({
            'destination_location_id': self.wh_karachi.lot_stock_id.id})
        self.assertEqual(requisition.node_id, self.gulshan)
        self.wh_karachi.node_id = self.karachi  # a correction of the set-up
        self.assertEqual(requisition.node_id, self.gulshan, "kept as it was made")
        counts = self.env['node.document.mixin']._update_documents(['livestock.requisition'])
        self.assertTrue(counts['livestock.requisition'])
        requisition.invalidate_recordset()
        self.assertEqual(requisition.node_id, self.karachi)

    def test_all_documents_have_their_sources(self):
        Mixin = self.env['node.document.mixin']
        models = Mixin._node_document_models()
        self.assertIn('livestock.slaugther', models)
        self.assertIn('welfare.line', models)
        for name in models:
            Model = self.env[name]
            self.assertIn('node_id', Model._fields)
            for path in Model._node_sources():
                self.assertIn(path.split('.')[0], Model._fields, "%s: unknown source %s" % (name, path))

    # ------------------------------------------------------------------
    # Livestock locations per warehouse
    # ------------------------------------------------------------------
    def test_livestock_locations_per_warehouse(self):
        karachi_meat = self.wh_karachi._livestock_location('meat')
        lahore_meat = self.wh_lahore._livestock_location('meat')
        self.assertNotEqual(karachi_meat, lahore_meat)
        self.assertEqual(karachi_meat.warehouse_id, self.wh_karachi)
        self.assertEqual(self.wh_karachi.livestock_meat_location_id, karachi_meat, "kept on the warehouse")
        self.assertEqual(self.wh_karachi._livestock_location('meat'), karachi_meat, "made once")
        # an existing location of that name in the warehouse is used
        cutting = self.env['stock.location'].create({'name': 'livestock cutting', 'usage': 'internal',
                                                     'location_id': self.wh_lahore.view_location_id.id})
        self.assertEqual(self.wh_lahore._livestock_location('cutting'), cutting)
        with self.assertRaises(ValidationError):
            self.wh_karachi.livestock_goat_location_id = lahore_meat  # another warehouse's location

    def test_slaughter_location(self):
        record = self.env['livestock.slaugther'].create({
            'product_id': self.product.id, 'quantity': 1, 'source_location_id': self.wh_karachi.lot_stock_id.id})
        self.assertEqual(record.slaughter_location_id, self.karachi_slaughter, "the warehouse's only one")
        # a second slaughter location: chosen by hand
        second = self.env['stock.location'].create({'name': 'LN Karachi Slaughter 2', 'usage': 'internal',
                                                    'location_id': self.wh_karachi.view_location_id.id,
                                                    'is_slaughter_location': True})
        other = self.env['livestock.slaugther'].create({
            'product_id': self.product.id, 'quantity': 1, 'source_location_id': self.wh_karachi.lot_stock_id.id})
        self.assertFalse(other.slaughter_location_id)
        with self.assertRaises(ValidationError):
            other.with_user(self.manager).action_confirm()
        other.slaughter_location_id = second
        other.with_user(self.manager).action_confirm()
        self.assertEqual(other._slaughtered_location(), second)
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, second), 1)

    def test_slaughter_flow_stays_in_its_warehouse(self):
        record = self.env['livestock.slaugther'].create({
            'product_id': self.product.id, 'quantity': 1, 'is_goat_depart': True,
            'source_location_id': self.wh_karachi.lot_stock_id.id,
        })
        self.assertEqual(record._livestock_warehouse(), self.wh_karachi)
        record.with_user(self.manager).action_confirm()
        goat = self.wh_karachi.livestock_goat_location_id
        self.assertTrue(goat, "the Goat department of the animal's warehouse")
        self.assertEqual(record._slaughtered_location(), goat)
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, goat), 1)

        record.with_user(self.manager).action_cutting()
        cutting = self.wh_karachi.livestock_cutting_location_id
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, goat), 0,
                         "cutting takes the animal from where Slaughtered put it")
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, cutting), 1)
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, self.wh_karachi.lot_stock_id, allow_negative=True), -1,
                         "only the Slaughtered transfer left the source location")
        self.assertEqual(record.cutting_material_id.warehouse_id, self.wh_karachi)
        self.assertFalse(self.wh_lahore.livestock_cutting_location_id, "Lahore is untouched")

    def test_order_transfer_then_bulk_transfer(self):
        record = self.env['livestock.slaugther'].create({
            'product_id': self.product.id, 'quantity': 1,
            'source_location_id': self.wh_karachi.lot_stock_id.id,
        })
        pen = self.env['stock.location'].create({'name': 'LN Pen', 'usage': 'internal',
                                                 'location_id': self.wh_karachi.view_location_id.id})
        waiting = record._slaughter_source_location()
        self.assertEqual(waiting.warehouse_id, self.wh_karachi)
        # Order Transfer (Draft): the animal is brought to where it waits for slaughter
        self.env['livestock.slaugther.wizard'].create({
            'livestock_slaughter_id': record.id, 'dest_location_id': pen.id,
        }).with_user(self.manager).action_do_transfer()
        self.assertEqual(record.order_transfer_picking_id.location_dest_id, waiting)
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, waiting), 1)
        with self.assertRaises(ValidationError):
            record._check_transfer_ready(bulk=False)  # once
        # Slaughtered takes it from there: nothing left behind
        record.with_user(self.manager).action_confirm()
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, waiting), 0)
        # Bulk Transfer: sent from where Slaughtered put it, then it cannot be cut
        self.env['livestock.slaugther.wizard'].create({
            'livestock_slaughter_ids': [(6, 0, record.ids)], 'is_bulk': True,
            'dest_location_id': self.wh_lahore.lot_stock_id.id, 'truck_number': 'LN-1',
        }).with_user(self.manager).action_do_transfer()
        self.assertEqual(record.transfer_picking_id.location_id, self.karachi_slaughter)
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, self.karachi_slaughter), 0)
        with self.assertRaises(ValidationError):
            record.with_user(self.manager).action_cutting()

    def test_document_rule(self):
        """T4: a switched user sees the documents of their Branches / Sites and their own."""
        group = self.env.ref('bn_stock_location.group_node_access')
        Requisition = self.env['livestock.requisition']
        karachi_doc = Requisition.create({'destination_location_id': self.wh_karachi.lot_stock_id.id})
        lahore_doc = Requisition.create({'destination_location_id': self.wh_lahore.lot_stock_id.id})
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ln lahore', 'login': 'ln_lahore',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('bn_livestock_slaugther.livestock_slaugther_menu_group').id,
                                  self.env.ref('bn_livestock_slaugther.livestock_slaugther_admin_group').id])],
            'allowed_node_ids': [(6, 0, self.lahore.ids)],
            # the old, location-based access: both warehouses
            'allowed_location_ids': [(6, 0, (self.wh_karachi.lot_stock_id | self.wh_lahore.lot_stock_id).ids)]})
        both = karachi_doc | lahore_doc
        self.assertEqual(Requisition.with_user(user).search([('id', 'in', both.ids)]), both, "not switched yet")
        user.groups_id = [(4, group.id)]
        own = Requisition.with_user(user).create({})
        visible = Requisition.with_user(user).search([('id', 'in', (both | own).ids)])
        self.assertEqual(visible, lahore_doc | own, "its Branch / Site and its own")
        user.all_nodes = True
        self.assertEqual(Requisition.with_user(user).search([('id', 'in', both.ids)]), both, "national")
