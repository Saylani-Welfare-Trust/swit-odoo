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
        def role(name, warehouse, flag):
            return Location.create({'name': name, 'usage': 'internal',
                                    'location_id': warehouse.view_location_id.id, flag: True})
        cls.karachi_goat = role('LN Karachi Goat', cls.wh_karachi, 'is_goat_location')
        cls.karachi_meat = role('LN Karachi Meat', cls.wh_karachi, 'is_meat_location')
        cls.karachi_cutting = role('LN Karachi Cutting', cls.wh_karachi, 'is_cutting_location')
        cls.lahore_cutting = role('LN Lahore Cutting', cls.wh_lahore, 'is_cutting_location')
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
        self.assertEqual(cutting.cutting_location_id, self.lahore_cutting, "the user's warehouse's only one")
        self.assertEqual(cutting.warehouse_id, self.wh_lahore)
        self.assertEqual(cutting.node_id, self.lahore)
        cutting.with_user(self.manager).action_validate_picking()
        Quant = self.env['stock.quant']
        self.assertEqual(Quant._get_available_quantity(self.product, self.lahore_cutting), 1,
                         "from its slaughter location into its cutting location")
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
    def test_several_locations_of_a_role(self):
        """A warehouse may hold several locations of a role: filled when there
        is only one, chosen otherwise, and only locations of that role offered."""
        Location = self.env['stock.location']
        self.assertEqual(Location._single_role_location('is_cutting_location', self.wh_karachi), self.karachi_cutting)
        second = Location.create({'name': 'LN Karachi Cutting 2', 'usage': 'internal', 'is_cutting_location': True,
                                  'location_id': self.wh_karachi.view_location_id.id})
        self.assertFalse(Location._single_role_location('is_cutting_location', self.wh_karachi), "two: chosen")
        self.assertEqual(Location._role_locations('is_cutting_location', self.wh_karachi), self.karachi_cutting | second)
        goat = self.env['livestock.slaugther'].create({
            'product_id': self.product.id, 'is_goat_depart': True, 'source_location_id': self.wh_karachi.lot_stock_id.id})
        self.assertIn(self.karachi_goat, goat.slaughter_location_option_ids)
        self.assertNotIn(self.karachi_slaughter, goat.slaughter_location_option_ids, "a goat goes to a Goat location")
        goat.slaughter_location_id = self.karachi_slaughter
        with self.assertRaises(ValidationError):
            goat.with_user(self.manager).action_confirm()  # not a Goat location

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
        self.assertEqual(record.slaughter_location_id, self.karachi_goat, "the warehouse's only Goat location")
        record.with_user(self.manager).action_confirm()
        goat = self.karachi_goat
        self.assertEqual(record._slaughtered_location(), goat)
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, goat), 1)
        self.assertEqual(record.cutting_location_id, self.karachi_cutting, "the warehouse's only cutting location")

        record.with_user(self.manager).action_cutting()
        cutting = self.karachi_cutting
        self.assertEqual(record._slaughter_source_location(), self.wh_karachi.lot_stock_id)
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, goat), 1,
                         "cutting takes the animal from the source location, not from where Slaughtered put it")
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, cutting), 1)
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, self.wh_karachi.lot_stock_id, allow_negative=True), -2,
                         "Slaughtered and Cutting both take from the source location")
        material = record.cutting_material_id
        self.assertEqual(material.cutting_location_id, cutting)
        self.assertEqual((material.meat_location_id, material.goat_location_id), (self.karachi_meat, self.karachi_goat))
        self.assertEqual(material.warehouse_id, self.wh_karachi)
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, self.lahore_cutting), 0,
                         "Lahore is untouched")

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
        # Bulk Transfer: sent from the source location, then it cannot be cut
        self.env['livestock.slaugther.wizard'].create({
            'livestock_slaughter_ids': [(6, 0, record.ids)], 'is_bulk': True,
            'dest_location_id': self.wh_lahore.lot_stock_id.id, 'truck_number': 'LN-1',
        }).with_user(self.manager).action_do_transfer()
        self.assertEqual(record.transfer_picking_id.location_id, waiting, "sent from the source location")
        self.assertEqual(record.source_location_id, self.wh_karachi.lot_stock_id, "the source location is kept")
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, self.karachi_slaughter), 1,
                         "what Slaughtered put there stays")
        self.assertEqual(self.env['stock.quant']._get_available_quantity(self.product, waiting, allow_negative=True), -1)
        with self.assertRaises(ValidationError):
            record.with_user(self.manager).action_cutting()

    def test_pos_location_is_the_source(self):
        """Slaughtered, Cutting and Bulk Transfer all take the animal from the
        location of the POS the order line came from, which stays its Source Location."""
        env = self.env
        pos_location = env['stock.location'].create({'name': 'LN Karachi POS', 'usage': 'internal',
                                                     'location_id': self.wh_karachi.view_location_id.id})
        picking_type = self.wh_karachi.out_type_id.copy({'name': 'LN POS Orders', 'sequence_code': 'LNPOS',
                                                         'default_location_src_id': pos_location.id})
        journal = env['account.journal'].create({'name': 'LN Cash', 'code': 'LNC', 'type': 'cash'})
        method = env['pos.payment.method'].create({'name': 'LN Cash', 'journal_id': journal.id})
        config = env['pos.config'].create({'name': 'LN Shop', 'picking_type_id': picking_type.id,
                                           'payment_method_ids': [(6, 0, method.ids)]})
        cut, sent = env['livestock.slaugther'].create([
            {'product_id': self.product.id, 'quantity': 1, 'is_goat_depart': True, 'pos_config_id': config.id}
            for _i in range(2)])
        self.assertEqual((cut.source_location_id, sent.source_location_id), (pos_location, pos_location))
        self.assertEqual(cut._slaughter_source_location(), pos_location)

        def qty(location):
            return env['stock.quant']._get_available_quantity(self.product, location, allow_negative=True)
        cut.with_user(self.manager).action_confirm()
        sent.with_user(self.manager).action_confirm()
        self.assertEqual((qty(pos_location), qty(self.karachi_goat)), (-2, 2), "Slaughtered: from the POS location")
        cut.with_user(self.manager).action_cutting()
        self.assertEqual((qty(pos_location), qty(self.karachi_cutting)), (-3, 1), "Cutting: from the POS location")
        env['livestock.slaugther.wizard'].create({
            'livestock_slaughter_ids': [(6, 0, sent.ids)], 'is_bulk': True,
            'dest_location_id': self.wh_lahore.lot_stock_id.id, 'truck_number': 'LN-2',
        }).with_user(self.manager).action_do_transfer()
        self.assertEqual(sent.transfer_picking_id.location_id, pos_location, "Bulk Transfer: from the POS location")
        self.assertEqual(qty(pos_location), -4)
        self.assertEqual((cut.source_location_id, sent.source_location_id), (pos_location, pos_location),
                         "the Source Location stays the POS location")

    def test_destination_rule(self):
        """A line is seen by the users whose analytic accounts include the one of its
        Destination Location: its Source (POS) location until a Bulk Transfer sends
        it elsewhere."""
        Slaughter = self.env['livestock.slaugther']
        self.wh_karachi.lot_stock_id.analytic_account_id = self.gulshan
        self.wh_lahore.lot_stock_id.analytic_account_id = self.lahore
        record = Slaughter.create({'product_id': self.product.id, 'quantity': 1,
                                   'source_location_id': self.wh_karachi.lot_stock_id.id})
        self.assertEqual(record.transfer_location, record.source_location_id, "it starts at its source")

        def user(login, node):
            return self.env['res.users'].with_context(no_reset_password=True).create({
                'name': login, 'login': login,
                'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                      self.env.ref('bn_livestock_slaugther.livestock_slaugther_menu_group').id,
                                      self.env.ref('bn_livestock_slaugther.livestock_slaugther_user_group').id])],
                'allowed_node_ids': [(6, 0, node.ids)]})
        karachi_user, lahore_user = user('ln_dest_k', self.gulshan), user('ln_dest_l', self.lahore)

        def seen_by(users):
            return tuple(bool(Slaughter.with_user(u).search([('id', '=', record.id)])) for u in users)
        self.assertEqual(seen_by((karachi_user, lahore_user)), (True, False), "the POS branch")
        record.state = 'slaughtered'
        self.env['livestock.slaugther.wizard'].create({
            'livestock_slaughter_ids': [(6, 0, record.ids)], 'is_bulk': True,
            'dest_location_id': self.wh_lahore.lot_stock_id.id, 'truck_number': 'LN-3',
        }).with_user(self.manager).action_do_transfer()
        self.assertEqual(record.transfer_location, self.wh_lahore.lot_stock_id)
        self.assertEqual(record.source_location_id, self.wh_karachi.lot_stock_id, "the source stays")
        self.assertEqual(seen_by((karachi_user, lahore_user)), (False, True), "the receiving location's users")

        # a Destination Location without an analytic account: no one (but unrestricted users)
        record = Slaughter.create({'product_id': self.product.id, 'quantity': 1,
                                   'source_location_id': self.karachi_cutting.id})
        self.assertFalse(self.karachi_cutting.analytic_account_id)
        self.assertEqual(seen_by((karachi_user, lahore_user)), (False, False))
        self.assertTrue(Slaughter.with_user(self.manager).search([('id', '=', record.id)]), "unrestricted")

        unsourced = Slaughter.create({'product_id': self.product.id, 'quantity': 1})
        self.assertTrue(unsourced.source_location_id, "a line not from a POS waits in its warehouse")
        self.assertEqual(unsourced.transfer_location, unsourced.source_location_id)

    def test_document_rule(self):
        """A user sees the documents of their Branches / Sites and their own."""
        Requisition = self.env['livestock.requisition']
        karachi_doc = Requisition.create({'destination_location_id': self.wh_karachi.lot_stock_id.id})
        lahore_doc = Requisition.create({'destination_location_id': self.wh_lahore.lot_stock_id.id})
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ln lahore', 'login': 'ln_lahore',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('bn_livestock_slaugther.livestock_slaugther_menu_group').id,
                                  self.env.ref('bn_livestock_slaugther.livestock_slaugther_admin_group').id])],
            'allowed_node_ids': [(6, 0, self.lahore.ids)]})
        both = karachi_doc | lahore_doc
        own = Requisition.with_user(user).create({})
        visible = Requisition.with_user(user).search([('id', 'in', (both | own).ids)])
        self.assertEqual(visible, lahore_doc | own, "its Branch / Site and its own")
        user.all_nodes = True
        self.assertEqual(Requisition.with_user(user).search([('id', 'in', both.ids)]), both, "national")
