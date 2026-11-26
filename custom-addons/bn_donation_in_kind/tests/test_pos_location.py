from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPosLocation(TransactionCase):
    """Goods given at a POS counter are received in that counter's warehouse."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.warehouse = env['stock.warehouse'].create({'name': 'DIN Counter WH', 'code': 'DINC'})
        cls.donor = env['res.partner'].create({'name': 'DIN Donor'})
        cls.product = env['product.product'].create({
            'name': 'DIN Rice', 'detailed_type': 'product', 'standard_price': 100, 'is_donation_in_kind': True})
        env['donation.in.kind.config'].search([]).unlink()

    def _create(self, warehouse):
        config = self.env['pos.config'].create({'name': 'DIN Counter', 'warehouse_id': warehouse.id})
        if not warehouse:
            config.warehouse_id = False
        session = self.env['pos.session'].create({'config_id': config.id, 'user_id': self.env.uid})
        Din = self.env['donation.in.kind'].with_context(pos_session_id=session.id)
        with patch.object(type(Din), '_send_din_notification', lambda self: {'status': 'success'}):
            return Din.create_din_record({'donor_id': self.donor.id, 'order_lines': [
                {'product_id': self.product.id, 'quantity': 2, 'remarks': '2 bags'}]})

    def test_counter_warehouse(self):
        result = self._create(self.warehouse)
        self.assertEqual(result['status'], 'success')
        din = self.env['donation.in.kind'].browse(result['id'])
        stock = self.warehouse.lot_stock_id
        self.assertEqual(din.location_id, stock)
        self.assertEqual(din.donation_in_kind_line_ids.location_id, stock)
        self.assertEqual(din.picking_type_id.warehouse_id, self.warehouse)

    def test_no_location(self):
        result = self._create(self.env['stock.warehouse'])
        self.assertEqual(result['status'], 'error', "a message, not a database error")
        self.assertFalse(self.env['donation.in.kind'].search([('donor_id', '=', self.donor.id)]))
