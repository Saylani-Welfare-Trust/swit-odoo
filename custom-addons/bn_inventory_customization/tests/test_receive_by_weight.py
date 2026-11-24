from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReceiveByWeight(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Product = env['product.product']
        category = env['product.category'].create({'name': 'Livestock T', 'property_cost_method': 'fifo',
                                                   'property_valuation': 'manual_periodic'})
        # the general product (Purchase Order, Material Request) and its variants by weight
        cls.cow = Product.create({'name': 'Cow T', 'detailed_type': 'product', 'check_stock': True,
                                  'purchase_ok': True, 'categ_id': category.id})
        cls.cow_12 = Product.create({'name': 'Cow - 12 T', 'detailed_type': 'product', 'categ_id': category.id})
        cls.cow_15 = Product.create({'name': 'Cow - 15 T', 'detailed_type': 'product', 'categ_id': category.id})
        cls.cow.product_tmpl_id.livestock_band_ids = [
            (0, 0, {'purchase_product_id': cls.cow.id, 'from_kg': 10, 'to_kg': 15, 'product_id': cls.cow_12.id}),
            (0, 0, {'purchase_product_id': cls.cow.id, 'from_kg': 15, 'to_kg': 30, 'product_id': cls.cow_15.id}),
        ]
        cls.vendor = env['res.partner'].create({'name': 'Livestock Vendor T'})

    def _order(self, qty=3, per_kg=100.0):
        order = self.env['purchase.order'].create({'partner_id': self.vendor.id, 'order_line': [(0, 0, {
            'product_id': self.cow.id, 'product_qty': qty, 'x_base_price': per_kg,
            'to_kg_multiplier': self.env['livestock.variant.line']._max_weight(self.cow)})]})
        # the procurement approvals (bn_procurement_workflow, when installed) are not what is tested here
        approvals = {f: True for f in ('cxo_approved', 'hod_approved', 'cfo_approved') if f in order._fields}
        if approvals:
            order.write(approvals)
        order.button_confirm()
        return order

    def _wizard(self, picking):
        action = picking.open_receive_by_weight_wizard()
        return self.env['receive.by.weight'].browse(action['res_id'])

    def test_bands(self):
        Band = self.env['livestock.variant.line']
        self.assertEqual(Band._find_band(self.cow, 14.99).product_id, self.cow_12)
        self.assertEqual(Band._find_band(self.cow, 15).product_id, self.cow_15, "to is excluded")
        self.assertFalse(Band._find_band(self.cow, 30))
        self.assertEqual(Band._max_weight(self.cow), 30)
        with self.assertRaises(ValidationError):  # overlaps 15-30
            Band.create({'purchase_product_id': self.cow.id, 'from_kg': 25, 'to_kg': 35, 'product_id': self.cow_15.id})
        with self.assertRaises(ValidationError):  # goes down
            Band.create({'purchase_product_id': self.cow.id, 'from_kg': 40, 'to_kg': 35, 'product_id': self.cow_15.id})
        with self.assertRaises(ValidationError):  # the general product itself
            Band.create({'purchase_product_id': self.cow.id, 'from_kg': 30, 'to_kg': 40, 'product_id': self.cow.id})

    def test_po_estimate_from_heaviest_band(self):
        order = self._order()
        self.assertEqual(order.order_line.price_unit, 100.0 * 30)

    def test_receive_distributes_over_variants(self):
        """Cow, 3 on the receipt: 12 kg x 2 and 15 kg x 1 -> Cow - 12: 2, Cow - 15: 1."""
        order = self._order()
        picking = order.picking_ids
        wizard = self._wizard(picking)
        self.assertEqual(len(wizard.line_ids), 1, "one line with all the units, to split by weight")
        self.assertEqual(wizard.line_ids.quantity, 3)
        first = wizard.line_ids
        first.write({'weight': 12, 'quantity': 2})
        self.env['receive.by.weight.line'].create({'wizard_id': wizard.id, 'move_id': first.move_id.id,
                                                    'weight': 15, 'quantity': 1})
        self.assertEqual(first.received_product_id, self.cow_12)
        self.assertEqual(wizard.total_quantity, 3)
        self.assertEqual(wizard.total_weight, 39)
        self.assertEqual(wizard.bill_amount, 39 * 100.0)
        wizard.action_receive()

        moves = picking.move_ids
        self.assertEqual(set(moves.product_id.ids), {self.cow_12.id, self.cow_15.id}, "Cow is replaced")
        cow_12 = moves.filtered(lambda m: m.product_id == self.cow_12)
        self.assertEqual((cow_12.product_uom_qty, cow_12.livestock_weight, cow_12.livestock_amount), (2, 24, 2400))
        picking.button_validate()
        self.assertEqual(picking.state, 'done')

        line = order.order_line
        self.assertEqual(line.qty_received, 3, "the variants are the line's receipt")
        self.assertEqual(self.cow_12.qty_available, 2)
        self.assertEqual(self.cow_15.qty_available, 1)
        self.assertAlmostEqual(cow_12._get_price_unit(), 1200.0)
        self.assertAlmostEqual(line._prepare_account_move_line()['price_unit'], 3900.0 / 3, places=2)

    def test_partial_receipt_leaves_a_backorder(self):
        order = self._order(qty=5)
        picking = order.picking_ids
        wizard = self._wizard(picking)
        wizard.line_ids.write({'weight': 20, 'quantity': 2})
        wizard.action_receive()
        general = picking.move_ids.filtered(lambda m: m.product_id == self.cow)
        self.assertEqual(general.product_uom_qty, 3, "the units not entered wait on the receipt")
        self.assertEqual(general.quantity, 0, "not validated as the general product")
        # validated now: the weighed units enter stock, the rest goes to a backorder
        action = picking.button_validate()
        if isinstance(action, dict) and action.get('res_model') == 'stock.backorder.confirmation':
            self.env['stock.backorder.confirmation'].with_context(action['context']).create({}).process()
        self.assertEqual(picking.state, 'done')
        self.assertEqual(self.cow.qty_available, 0, "no unweighed Cow in stock")
        backorder = picking.backorder_ids
        self.assertEqual(backorder.move_ids.product_id, self.cow)
        self.assertEqual(backorder.move_ids.product_uom_qty, 3)
        picking = backorder
        # the rest is received later, by a new wizard
        second = self._wizard(picking)
        self.assertEqual(second.line_ids.quantity, 3)
        second.line_ids.write({'weight': 12, 'quantity': 3})
        second.action_receive()
        self.assertFalse(picking.move_ids.filtered(lambda m: m.product_id == self.cow))
        self.assertEqual(sum(picking.move_ids.mapped('product_uom_qty')), 3)
        picking.button_validate()
        self.assertEqual(order.order_line.qty_received, 5)
        self.assertEqual(self.cow_15.qty_available, 2)
        self.assertEqual(self.cow_12.qty_available, 3)
        self.assertAlmostEqual(order.order_line._prepare_account_move_line()['price_unit'],
                               (2 * 20 + 3 * 12) * 100.0 / 5, places=2)

    def test_refused(self):
        order = self._order(qty=2)
        picking = order.picking_ids
        wizard = self._wizard(picking)
        wizard.line_ids.write({'weight': 45, 'quantity': 2})
        with self.assertRaises(UserError):  # no band holds 45 kg
            wizard.action_receive()
        wizard.line_ids.write({'weight': 12, 'quantity': 3})
        with self.assertRaises(UserError):  # more units than on the receipt
            wizard.action_receive()
        wizard.line_ids.write({'weight': 12, 'quantity': 1.5})
        with self.assertRaises(UserError):  # not a whole number
            wizard.action_receive()
        wizard.line_ids.write({'weight': 12, 'quantity': 2})
        wizard.action_receive()
        with self.assertRaises(UserError):  # once
            wizard.action_receive()

    def test_variant_not_bought_directly(self):
        with self.assertRaises(ValidationError):
            self.env['purchase.order'].create({'partner_id': self.vendor.id, 'order_line': [(0, 0, {
                'product_id': self.cow_12.id, 'product_qty': 1})]})
