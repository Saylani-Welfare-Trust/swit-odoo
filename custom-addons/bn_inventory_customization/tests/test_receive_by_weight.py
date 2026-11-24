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
        cls.goat = Product.create({'name': 'Goat (purchase) T', 'detailed_type': 'product', 'check_stock': True,
                                   'purchase_ok': True, 'categ_id': category.id})
        cls.small = Product.create({'name': 'Goat Sadqa Small T', 'detailed_type': 'product', 'categ_id': category.id})
        cls.big = Product.create({'name': 'Goat Sadqa Big T', 'detailed_type': 'product', 'categ_id': category.id})
        cls.sadqa = env['livestock.variant'].create({'name': 'Sadqa T', 'line_ids': [
            (0, 0, {'purchase_product_id': cls.goat.id, 'from_kg': 10, 'to_kg': 20, 'product_id': cls.small.id}),
            (0, 0, {'purchase_product_id': cls.goat.id, 'from_kg': 20, 'to_kg': 30, 'product_id': cls.big.id}),
        ]})
        cls.vendor = env['res.partner'].create({'name': 'Livestock Vendor T'})

    def _order(self, qty=3, per_kg=100.0):
        order = self.env['purchase.order'].create({'partner_id': self.vendor.id, 'order_line': [(0, 0, {
            'product_id': self.goat.id, 'product_qty': qty, 'x_base_price': per_kg,
            'to_kg_multiplier': self.env['livestock.variant.line']._max_weight(self.goat)})]})
        # the procurement approvals (bn_procurement_workflow, when installed) are not what is tested here
        approvals = {f: True for f in ('cxo_approved', 'hod_approved', 'cfo_approved') if f in order._fields}
        if approvals:
            order.write(approvals)
        order.button_confirm()
        return order

    def test_bands(self):
        Band = self.env['livestock.variant.line']
        self.assertEqual(Band._find_band(self.sadqa, self.goat, 19.99).product_id, self.small)
        self.assertEqual(Band._find_band(self.sadqa, self.goat, 20).product_id, self.big, "to is excluded")
        self.assertFalse(Band._find_band(self.sadqa, self.goat, 30))
        self.assertEqual(Band._max_weight(self.goat), 30)
        with self.assertRaises(ValidationError):
            Band.create({'variant_id': self.sadqa.id, 'purchase_product_id': self.goat.id,
                         'from_kg': 25, 'to_kg': 35, 'product_id': self.big.id})
        with self.assertRaises(ValidationError):
            Band.create({'variant_id': self.sadqa.id, 'purchase_product_id': self.goat.id,
                         'from_kg': 40, 'to_kg': 35, 'product_id': self.big.id})

    def test_po_estimate_from_heaviest_band(self):
        order = self._order()
        self.assertEqual(order.order_line.price_unit, 100.0 * 30)

    def test_receive_value_and_bill(self):
        order = self._order()
        picking = order.picking_ids
        action = picking.open_receive_by_weight_wizard()
        wizard = self.env['receive.by.weight'].browse(action['res_id'])
        self.assertEqual(len(wizard.line_ids), 3)
        self.assertEqual(wizard.line_ids.livestock_variant, self.sadqa, "the only variant of the product is preset")
        for line, weight in zip(wizard.line_ids, (12, 20, 25)):
            line.weight = weight
        self.assertEqual(wizard.bill_amount, (12 + 20 + 25) * 100.0)
        wizard.action_receive()

        moves = picking.move_ids
        self.assertEqual(set(moves.product_id.ids), {self.small.id, self.big.id})
        big = moves.filtered(lambda m: m.product_id == self.big)
        self.assertEqual(big.product_uom_qty, 2)
        self.assertEqual(big.livestock_weight, 45)
        self.assertEqual(big.livestock_amount, 4500)
        picking.button_validate()
        self.assertEqual(picking.state, 'done')

        line = order.order_line
        self.assertEqual(line.qty_received, 3, "the weighed units are the line's receipt")
        self.assertEqual(self.small.qty_available, 1)
        self.assertEqual(self.big.qty_available, 2)
        self.assertAlmostEqual(big._get_price_unit(), 2250.0)
        bill_vals = line._prepare_account_move_line()
        self.assertAlmostEqual(bill_vals['price_unit'], 5700.0 / 3, places=2)

    def test_weight_outside_every_band_refused(self):
        order = self._order(qty=1)
        action = order.picking_ids.open_receive_by_weight_wizard()
        wizard = self.env['receive.by.weight'].browse(action['res_id'])
        wizard.line_ids.weight = 45
        with self.assertRaises(UserError):
            wizard.action_receive()
