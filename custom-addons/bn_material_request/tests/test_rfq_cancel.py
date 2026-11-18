from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRfqCancelReleasesQuantity(TransactionCase):
    """The quantity of a Purchase Request line sent out on a batch of RFQs is
    available again once every RFQ of the batch is cancelled."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env['product.product'].create({'name': 'PR Rice', 'detailed_type': 'consu'})
        cls.vendor_a = cls.env['res.partner'].create({'name': 'PR Vendor A'})
        cls.vendor_b = cls.env['res.partner'].create({'name': 'PR Vendor B'})
        cls.requisition = cls.env['purchase.requisition'].create({
            'line_ids': [(0, 0, {'product_id': cls.product.id, 'product_qty': 10})],
        })
        cls.line = cls.requisition.line_ids

    def _rfq(self, vendor):
        return self.env['purchase.order'].create({
            'partner_id': vendor.id,
            'requisition_id': self.requisition.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_qty': 10, 'price_unit': 1})],
        })

    def test_quantity_back_once_every_rfq_of_the_batch_is_cancelled(self):
        rfq_a, rfq_b = self._rfq(self.vendor_a), self._rfq(self.vendor_b)
        self.line._lock_quantity(10, rfq_a | rfq_b)
        self.assertTrue(self.line.is_locked)

        rfq_a.button_cancel()
        self.assertTrue(self.line.is_locked, "the other vendor's RFQ still quotes for it")
        self.assertEqual(self.line.remaining_qty, 0)

        rfq_b.button_cancel()
        self.assertFalse(self.line.is_locked)
        self.assertEqual(self.line.remaining_qty, 10)

        # set back to draft: the RFQ takes the quantity again
        rfq_b.button_draft()
        self.assertTrue(self.line.is_locked)
        self.assertEqual(self.line.remaining_qty, 0)

    def test_set_to_draft_refused_once_sent_out_again(self):
        rfq = self._rfq(self.vendor_a)
        self.line._lock_quantity(10, rfq)
        rfq.button_cancel()
        self.assertEqual(self.line.remaining_qty, 10)

        self.line._lock_quantity(10, self._rfq(self.vendor_b))
        with self.assertRaises(ValidationError):
            rfq.button_draft()
